#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created On: 2023-01-01
@Author: PanMaster团队
百度网盘客户端实现
"""

from __future__ import annotations

import logging  # 导入标准日志模块
import os
import re

from collections import deque
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import parse_qs, urlparse

from backend.app.coulddrive.schema.enum import DriveType
from backend.app.coulddrive.schema.file import (
    BaseFileInfo,
    BaseShareInfo,
    CancelShareParam,
    CopyParam,
    ListFilesParam,
    ListShareFilesParam,
    ListShareInfoParam,
    MkdirParam,
    MoveParam,
    RelationshipParam,
    RelationshipType,
    RemoveParam,
    RenameParam,
    ShareParam,
    TransferParam,
    UserInfoParam,
)
from backend.app.coulddrive.schema.user import (
    BaseUserInfo,
    GetUserFriendDetail,
    GetUserGroupDetail,
)
from backend.app.coulddrive.service.baidu.api import BaiduApi
from backend.app.coulddrive.service.baidu.errors import BaiduApiError
from backend.app.coulddrive.service.coulddrive_service import (
    BaseDriveClient,
    ConfigItem,
    ConfigItemType,
    DriveAuthError,
    DriverRegistry,
)
from backend.utils.timezone import timezone

from .schemas import (
    FromTo,
    PcsFile,
    PcsQuota,
    PcsSharedLink,
    PcsSharedPath,
)

SHARED_URL_PREFIX = 'https://pan.baidu.com/s/'


def _unify_shared_url(url: str) -> str:
    """统一输入的分享链接格式"""

    # 标准链接格式
    temp = r'pan\.baidu\.com/s/(.+?)(\?|$)'
    m = re.search(temp, url)
    if m:
        return SHARED_URL_PREFIX + m.group(1)

    # surl 链接格式
    temp = r'baidu\.com.+?\?surl=(.+?)(\?|$)'
    m = re.search(temp, url)
    if m:
        return SHARED_URL_PREFIX + '1' + m.group(1)

    raise ValueError(f'The shared url is not a valid url. {url}')


def _extract_shorturl_from_url(url: str) -> str:
    """从分享链接中提取短链接ID"""

    # 标准链接格式：https://pan.baidu.com/s/1xxxxx
    temp = r'pan\.baidu\.com/s/1?(.+?)(\?|$)'
    m = re.search(temp, url)
    if m:
        return m.group(1)

    # surl 链接格式
    temp = r'baidu\.com.+?\?surl=(.+?)(\?|&|$)'
    m = re.search(temp, url)
    if m:
        return m.group(1)

    # 如果输入的就是短链接ID，直接返回
    if not ('http' in url or 'baidu' in url):
        return url

    raise ValueError(f'无法从分享链接中提取短链接ID: {url}')


@DriverRegistry.register(DriveType.BAIDU_DRIVE)
class BaiduClient(BaseDriveClient):
    """百度网盘 PCS API 驱动

    这是对`BaiduPCS`的封装。它将原始BaiduPCS请求的响应内容解析为一些内部数据结构。

    支持的认证方式：
    - Cookie 字符串（向后兼容）
    - 配置字典 {"cookie": "BDUSS=xxx;STOKEN=xxx"}
    """

    # 百度认证相关错误码
    AUTH_ERROR_CODES: set[int] = {-4, -5, -6, -11, 3, 31041, 31042, 31044, 31045}

    # ========== 驱动配置项声明 ==========

    @classmethod
    def get_config_items(cls) -> List[ConfigItem]:
        """声明百度网盘需要的配置项"""
        return [
            ConfigItem(
                name='cookie',
                label='Cookie',
                type=ConfigItemType.STRING,
                required=True,
                description='百度网盘 Cookie，需包含 BDUSS 和 STOKEN',
                placeholder='BDUSS=xxx;STOKEN=xxx',
            ),
        ]

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> Dict[str, List[str]]:
        """验证百度网盘配置"""
        result = {'errors': [], 'warnings': []}

        cookie = config.get('cookie', '')

        if not cookie:
            result['errors'].append('缺少必需参数: Cookie')
            return result

        # 检查关键字段
        if 'BDUSS' not in cookie:
            result['errors'].append('Cookie 中缺少 BDUSS')

        if 'STOKEN' not in cookie:
            result['warnings'].append('建议提供 STOKEN 以获得完整功能')

        # 检查长度
        if len(cookie) < 50:
            result['warnings'].append('Cookie 长度似乎过短，请检查是否完整')

        return result

    def __init__(self, config: Union[str, Dict[str, Any]], user_id: Optional[int] = None, **kwargs):
        """
        初始化百度网盘驱动

        :param config: 认证配置
            - str: cookie 字符串（向后兼容）
            - dict: 配置字典 {"cookie": "BDUSS=xxx;STOKEN=xxx"}
        :param user_id: 用户ID
        """
        # 调用父类初始化（处理 config 转换）
        super().__init__(config, **kwargs)

        # 初始化日志记录器
        self.logger = logging.getLogger(self.__class__.__name__)

        # 不要先创建空的 BaiduApi 实例，直接在 login 中创建
        self._baidupcs: BaiduApi = None
        self._is_authorized = False

        # 从配置中获取 cookie
        cookies = self.get_config_value('cookie', '')

        # 自动登录
        if self.login(cookies, user_id):
            pass
        else:
            raise ValueError('BaiduClient 初始化失败：登录失败')

    @property
    def drive_type(self) -> str:
        return 'BaiduDrive'

    def login(self, cookies: str, user_id: Optional[int] = None) -> bool:
        """
        登录百度网盘

        :param cookies: cookies 字符串，格式如 "BDUSS=xxx; STOKEN=xxx; PTOKEN=xxx"
        :param user_id: 用户ID
        :return: 是否登录成功
        """
        # 检查是否有有效的认证信息
        has_cookies = cookies and cookies.strip()

        if has_cookies:
            try:
                self._baidupcs = BaiduApi(cookies=cookies, user_id=user_id)

                if self._baidupcs._bduss:
                    # 通过获取用户信息来验证登录并设置用户ID
                    try:
                        import asyncio

                        async def verify_login():
                            user_info_response = await self._baidupcs.get_user_info()
                            if isinstance(user_info_response, dict):
                                user_info = user_info_response.get('user_info', {})
                                if isinstance(user_info, dict):
                                    user_id = int(user_info.get('uk')) if user_info.get('uk') is not None else None
                                    if user_id:
                                        self._baidupcs._user_id = user_id
                                        return True
                            return False

                        # 尝试在当前上下文中运行验证
                        try:
                            asyncio.get_running_loop()
                            # 在异步上下文中，暂时标记为已授权，用户ID稍后获取
                            self._is_authorized = True
                            return True
                        except RuntimeError:
                            # 在同步上下文中，立即验证登录
                            login_verified = asyncio.run(verify_login())
                            self._is_authorized = login_verified
                            return login_verified

                    except Exception as e:
                        self.logger.debug(f'登录验证失败: {e}')
                        self._is_authorized = False
                        return False

                self._is_authorized = False
                return False
            except Exception as e:
                self.logger.error(f'BaiduApi 初始化失败: {e}')
                self._is_authorized = False
                return False

        # 如果没有认证信息且_baidupcs为None，返回False
        if self._baidupcs is None:
            self._is_authorized = False
            return False

        return self._is_authorized

    @property
    def bduss(self) -> str:
        return self._baidupcs._bduss if self._baidupcs else ''

    @property
    def bdstoken(self) -> str:
        return self._baidupcs.bdstoken if self._baidupcs else ''

    @property
    def stoken(self) -> Optional[str]:
        return self._baidupcs._stoken if self._baidupcs else None

    @property
    def ptoken(self) -> Optional[str]:
        return self._baidupcs._ptoken if self._baidupcs else None

    @property
    def baiduid(self) -> Optional[str]:
        return self._baidupcs._baiduid if self._baidupcs else None

    @property
    def logid(self) -> Optional[str]:
        return self._baidupcs._logid if self._baidupcs else None

    @property
    def user_id(self) -> Optional[int]:
        """获取用户ID，如果没有则返回None"""
        if self._baidupcs and self._baidupcs._user_id:
            return self._baidupcs._user_id
        return None

    @property
    def cookies(self) -> Dict[str, str]:
        return self._baidupcs.cookies if self._baidupcs else {}

    async def quota(self) -> PcsQuota:
        """获取配额信息"""

        info = await self._baidupcs.quota()
        return PcsQuota(quota=info['quota'], used=info['used'])

    async def get_user_info(self, params: UserInfoParam = None, **kwargs) -> BaseUserInfo:
        """
        获取用户信息

        参数:
            params (UserInfoParam): 用户信息查询参数（可选）
            **kwargs: 其他关键字参数

        返回:
            BaseUserInfo: 用户信息
        """
        try:
            user_info_response = await self._baidupcs.get_user_info()
            user_quota_response = await self._baidupcs.quota()

            if isinstance(user_info_response, dict) and user_info_response.get('error_code') == 0:
                # 从 user_info 字段中提取数据
                user_info = user_info_response.get('user_info', {})

                return BaseUserInfo(
                    user_id=str(user_info.get('uk', 0)),
                    username=user_info.get('username', ''),
                    avatar_url=user_info.get('photo', ''),
                    quota=user_quota_response.get('quota', 0),
                    used=user_quota_response.get('used', 0),
                    is_vip=bool(user_info.get('is_vip', 0)),
                    is_supervip=bool(user_info.get('is_svip', 0)),
                )
            else:
                error_msg = (
                    user_info_response.get('error_msg', '未知错误')
                    if isinstance(user_info_response, dict)
                    else str(user_info_response)
                )
                self.logger.error(f'获取用户信息失败: {error_msg}')
                return BaseUserInfo(user_id='0', username='未知用户', avatar_url='', is_vip=False, is_supervip=False)
        except Exception as e:
            if self._is_auth_error(e):
                raise DriveAuthError(str(e), drive_type=self.drive_type) from e
            self.logger.error(f'获取用户信息时发生错误: {e}')
            return BaseUserInfo(user_id='0', username='未知用户', avatar_url='', is_vip=False, is_supervip=False)

    async def meta(self, *file_paths: str) -> List[PcsFile]:
        """获取`file_paths`的元数据"""

        info = await self._baidupcs.meta(*file_paths)
        return [PcsFile.from_(v) for v in info.get('list', [])]

    async def exists(self, file_path: str) -> bool:
        """检查`file_path`是否存在"""

        return await self._baidupcs.exists(file_path)

    async def is_file(self, file_path: str) -> bool:
        """检查`file_path`是否是文件"""

        return await self._baidupcs.is_file(file_path)

    async def is_dir(self, file_path: str) -> bool:
        """检查`file_path`是否是目录"""

        return await self._baidupcs.is_dir(file_path)

    async def get_disk_list(self, params: ListFilesParam, **kwargs: Any) -> List[BaseFileInfo]:
        """
        获取目录下的文件和目录列表（单层，不递归）

        :param params: 文件列表查询参数
        :param kwargs: 其他关键字参数
        """
        # 从 params 中提取参数
        file_path = params.file_path or '/'
        file_id = params.file_id or ''
        desc = params.desc
        name = params.name
        time = params.time
        size = params.size_sort

        # 确保路径格式正确
        if not file_path.startswith('/'):
            file_path = '/' + file_path

        drive_files_list: List[BaseFileInfo] = []
        initial_parent_id = file_id

        async def fetch_all_pages_from_api(target_file_path: str, **api_params) -> List[Dict]:
            """
            自动翻页获取指定路径下的所有文件/目录（单层）

            :param target_file_path: 目标路径
            :param api_params: API参数（如desc、name、time、size）
            :return: 所有页面的文件列表
            """
            page = 1
            page_size = 100
            all_items = []

            while True:
                try:
                    info = await self._baidupcs.list_with_pagination(
                        target_file_path, page=page, num=page_size, **api_params
                    )
                    current_items = info.get('list', [])
                    all_items.extend(current_items)

                    # 如果本页返回数量小于page_size，说明已经是最后一页
                    if len(current_items) < page_size:
                        break

                    page += 1
                except Exception as e:
                    if self._is_auth_error(e):
                        raise DriveAuthError(str(e), drive_type=self.drive_type) from e
                    self.logger.error(f"获取第{page}页数据失败 '{target_file_path}': {e}")
                    break

            return all_items

        try:
            items_raw = await fetch_all_pages_from_api(file_path, desc=desc, name=name, time=time, size=size)
        except DriveAuthError:
            raise
        except Exception as e:
            self.logger.error(f"Error listing path '{file_path}': {e}")
            return []

        # 将API返回的数据转换为BaseFileInfo
        for item_dict in items_raw:
            file_instance = BaseFileInfo(
                file_id=str(item_dict.get('fs_id', '')),
                file_path=item_dict.get('path', ''),
                file_name=item_dict.get('server_filename', ''),
                file_size=item_dict.get('size'),
                is_folder=bool(item_dict.get('isdir', 0)),
                created_at=str(item_dict.get('server_ctime', '')),
                updated_at=str(item_dict.get('server_mtime', '')),
                parent_id=str(initial_parent_id) if initial_parent_id is not None else '',
            )
            drive_files_list.append(file_instance)

        return drive_files_list

    def search(self, keyword: str, file_path: str, recursive: bool = False) -> List[PcsFile]:
        """在`file_path`中搜索`keyword`"""

        info = self._baidupcs.search(keyword, file_path, recursive=recursive)
        pcs_files = []
        for file_info in info['list']:
            pcs_files.append(PcsFile.from_(file_info))
        return pcs_files

    async def mkdir(self, params: MkdirParam, **kwargs: Any) -> BaseFileInfo:
        """创建目录

        Args:
            file_path: 完整的目录路径
            parent_id: 父目录ID (百度网盘不使用此参数，但为保持接口兼容性保留)
            file_name: 目录名称 (百度网盘不使用此参数，但为保持接口兼容性保留)
            return_if_exist: 如果目录已存在，是否返回已存在目录的信息
            *args: 其他位置参数
            **kwargs: 其他关键字参数

        Returns:
            BaseFileInfo: 创建的目录信息

        Raises:
            BaiduApiError: 创建目录失败时抛出
        """
        file_path = params.file_path
        parent_id = params.parent_id
        return_if_exist = params.return_if_exist

        # 规范化路径
        if not file_path.startswith('/'):
            file_path = '/' + file_path

        # 百度网盘使用完整路径创建目录，不需要额外拼接 file_name
        # file_path 已经是完整的目标路径，如 "/同步测试/四六级说明"
        # 不应该再拼接 file_name，否则会变成 "/同步测试/四六级说明/四六级说明"

        try:
            # 检查目录是否已存在
            if return_if_exist and await self.exists(file_path):
                # 获取已存在目录的信息
                meta_info = await self.meta(file_path)
                if meta_info and len(meta_info) > 0:
                    pcs_file = meta_info[0]
                    return BaseFileInfo(
                        file_id=str(pcs_file.fs_id),
                        file_path=pcs_file.path,
                        file_name=os.path.basename(pcs_file.path),
                        is_folder=True,
                        file_size=0,
                        created_at=str(pcs_file.server_ctime) if pcs_file.server_ctime else '',
                        updated_at=str(pcs_file.server_mtime) if pcs_file.server_mtime else '',
                        parent_id=parent_id if parent_id else str(os.path.dirname(pcs_file.path)),
                    )

            # 创建新目录
            info = await self._baidupcs.makedir(file_path)
            pcs_file = PcsFile.from_(info)

            return BaseFileInfo(
                file_id=str(pcs_file.fs_id),
                file_path=pcs_file.path,
                file_name=os.path.basename(pcs_file.path),
                is_folder=True,
                file_size=0,
                created_at=str(pcs_file.server_ctime) if pcs_file.server_ctime else '',
                updated_at=str(pcs_file.server_mtime) if pcs_file.server_mtime else '',
                parent_id=parent_id if parent_id else str(os.path.dirname(pcs_file.path)),
            )

        except BaiduApiError as e:
            self.logger.error(f'创建目录失败: {e}')
            raise

    async def move(self, params: 'MoveParam', **kwargs: Any) -> bool:
        """移动文件或目录"""
        try:
            # 百度网盘使用路径进行移动操作
            if params.file_paths and params.target_path:
                # 使用路径方式
                all_paths = params.file_paths + [params.target_path]
                info = await self._baidupcs.move(*all_paths)
            else:
                self.logger.error('百度网盘移动操作需要提供 file_paths 和 target_path')
                return False

            r = info['extra'].get('list')
            if not r:
                self.logger.error('移动文件失败: 返回列表为空')
                return False
            return True
        except Exception as e:
            self.logger.error(f'移动文件时发生错误: {e}')
            return False

    async def rename(self, params: RenameParam, **kwargs: Any) -> FromTo:
        """重命名文件"""
        source = params.file_path
        dest = params.new_path
        try:
            info = await self._baidupcs.rename(source, dest)
            r = info['extra'].get('list')
            if not r:
                self.logger.error('重命名文件失败: 返回列表为空')
                return False
            # 如果需要，这里可以保留 FromTo 对象的构建或日志记录，但最终返回 True
            # v = r[0]
            # FromTo(from_=v["from"], to_=v["to"])
            return True
        except Exception as e:
            self.logger.error(f'重命名文件时发生错误: {e}')
            return False

    async def copy(self, params: 'CopyParam', **kwargs: Any) -> bool:
        """复制文件或目录"""
        try:
            # 百度网盘使用路径进行复制操作
            if params.file_paths and params.target_path:
                # 使用路径方式
                all_paths = params.file_paths + [params.target_path]
                info = await self._baidupcs.copy(*all_paths)
            else:
                self.logger.error('百度网盘复制操作需要提供 file_paths 和 target_path')
                return False

            r = info['extra'].get('list')
            if not r:
                self.logger.error('复制文件失败: 返回列表为空')
                return False
            return True
        except Exception as e:
            self.logger.error(f'复制文件时发生错误: {e}')
            return False

    async def remove(self, params: RemoveParam, **kwargs: Any) -> bool:
        """删除文件或目录"""
        file_paths = params.file_paths
        file_ids = params.file_ids
        try:
            paths_for_api_call = []

            input_paths_list = []
            if isinstance(file_paths, str):
                input_paths_list = [file_paths] if file_paths else []
            elif isinstance(file_paths, list):
                input_paths_list = file_paths

            # 如果提供了 file_paths，优先使用它们，并确保它们是绝对路径
            if input_paths_list:
                for path in input_paths_list:
                    if not path:
                        continue

                    current_path_to_delete = path
                    if not current_path_to_delete.startswith('/'):
                        current_path_to_delete = '/' + current_path_to_delete
                    paths_for_api_call.append(current_path_to_delete)

            elif file_ids and not input_paths_list:
                self.logger.error(
                    'BaiduClient.remove 不支持单独使用 file_ids 删除，除非实现可靠的ID到路径转换或百度提供基于ID的删除API。'
                    '请同时提供对应的 file_paths。'
                )
                return False
            elif not input_paths_list and not file_ids:
                self.logger.warning('没有提供 file_paths 或 file_ids 进行删除操作。')
                return False  # 或者 True，因为没有操作也算成功？

            if not paths_for_api_call:
                # self.logger.info("处理输入后，没有可供删除的有效路径。")
                # 如果初始输入非空但最终没有可操作路径（例如，所有路径都不存在并被跳过），
                # 返回True表示操作完成且无错误，或False表示未达到预期删除效果。
                # 此处返回True表示"尝试删除，但没有符合条件的目标"。
                return True

            # 使用收集到的所有有效路径，一次性调用底层API
            await self._baidupcs.remove(*paths_for_api_call)
            # self.logger.info(f"已成功请求删除以下路径: {paths_for_api_call}")
            if file_ids:  # 如果也提供了ID，可以一起记录，方便追踪
                self.logger.debug(f'对应的 file_ids (如果提供): {file_ids}')

            return True

        except BaiduApiError as e:
            # 此处捕获由 _baidupcs.remove 或其他百度API调用（如 self.exists）抛出的 BaiduApiError
            msg = e.message if hasattr(e, 'message') and e.message else str(e)
            self.logger.error(f'删除文件/目录时发生百度API错误: {msg}')
            raise  # 将 BaiduApiError 重新抛出，由上层 (server.py) 处理
        except Exception as e_generic:
            # 捕获其他未预料的错误
            self.logger.error(f'删除文件/目录时发生未知错误: {str(e_generic)}')
            # 将未知错误包装成 BaiduApiError 再抛出
            raise BaiduApiError(f'删除文件/目录失败 (未知错误): {str(e_generic)}')

    async def create_share(self, params: ShareParam, **kwargs: Any) -> BaseShareInfo:
        """
        创建分享链接

        :param params: 分享参数
        :param kwargs: 其他关键字参数
        :return: 分享信息
        """
        file_name = params.file_name
        file_ids = params.file_ids
        expired_type = params.expired_type
        password = params.password

        try:
            # 调用改进后的share方法
            info = await self._baidupcs.share(file_ids=file_ids, password=password or '', period=expired_type)

            # 直接解析返回结果，不需要判断errno（装饰器已处理）
            from datetime import datetime

            # 直接使用API返回的过期时间
            expired_at = None
            if info.get('expiretime'):
                expired_at = datetime.fromtimestamp(info.get('expiretime'), tz=timezone.tz_info)

            return BaseShareInfo(
                title=file_name,
                share_id=str(info.get('shareid', '')),
                pwd_id='',  # 百度网盘不提供pwd_id
                url=info.get('link', ''),
                password=info.get('passwd', ''),
                expired_type=expired_type,
                view_count=0,
                expired_at=expired_at,
                expired_left=None,
                audit_status=1,  # 假设通过审核
                status=1,
                file_id=str(file_ids[0]) if file_ids else None,
                file_only_num=None,
                file_size=None,
                path_info=None,
            )

        except BaiduApiError as e:
            self.logger.error(f'创建分享时发生百度API错误: {e}')
            raise
        except Exception as e:
            self.logger.error(f'创建分享时发生未知错误: {e}')
            raise BaiduApiError(f'创建分享失败: {str(e)}')

    async def list_shared(self, page: int = 1, size: int = 20) -> List[PcsSharedLink]:
        """列出某页的分享链接

        要使用此API，`cookies`中必须包含`STOKEN`
        """

        info = await self._baidupcs.get_share_page(page, size)
        return [PcsSharedLink.from_(v) for v in info['list']]

    def shared_password(self, share_id: int) -> Optional[str]:
        """显示分享链接密码

        要使用此API，`cookies`中必须包含`STOKEN`
        """

        info = self._baidupcs.shared_password(share_id)
        p = info.get('pwd', '0')
        if p == '0':
            return None
        return p

    async def _shared_paths(self, shared_url: str) -> List[PcsSharedPath]:
        """获取`shared_url`的共享路径"""

        info = await self._baidupcs.shared_paths(shared_url)
        uk = info.get('share_uk') or info.get('uk')
        uk = int(uk)

        assert uk, "`BaiduPCSApi.shared_paths`: Don't get `uk`"

        share_id = info['shareid']
        bdstoken = info['bdstoken']

        if not info.get('file_list'):
            return []

        if isinstance(info['file_list'], list):
            file_list = info['file_list']
        elif isinstance(info['file_list'].get('list'), list):
            file_list = info['file_list']['list']
        else:
            raise ValueError('`shared_paths`: Parsing shared info fails')

        return [PcsSharedPath.from_(v)._replace(uk=uk, share_id=share_id, bdstoken=bdstoken) for v in file_list]

    async def _list_shared_paths(
        self,
        sharedpath: str,
        uk: int,
        share_id: int,
        bdstoken: str,
        page: int = 1,
        size: int = 100,
    ) -> List[PcsSharedPath]:
        """共享目录`sharedpath`的子共享路径"""

        info = await self._baidupcs.list_shared_paths(sharedpath, uk, share_id, page=page, size=size)
        return [PcsSharedPath.from_(v)._replace(uk=uk, share_id=share_id, bdstoken=bdstoken) for v in info['list']]

    async def _transfer_shared_paths(
        self,
        remotedir: str,
        fs_ids: List[int],
        uk: int,
        share_id: int,
        bdstoken: str,
        shared_url: str,
    ):
        """保存这些共享路径的`fs_ids`到`remotedir`"""

        await self._baidupcs.transfer_shared_paths(remotedir, fs_ids, uk, share_id, bdstoken, shared_url)

    # save_shared 已内联至 transfer 的 link 分支，避免额外公开方法

    async def remote_path_exists(self, name: str, rd: str, _cache: Dict[str, Set[str]] | None = None) -> bool:
        """检查远程路径是否存在"""
        if _cache is None:
            _cache = {}

        names = _cache.get(rd)
        if names is None:
            try:
                # 复用 get_disk_list 单层列目录
                params = ListFilesParam(drive_type=self.drive_type, file_path=rd)
                items = await self.get_disk_list(params)
                names = set([PurePosixPath(i.file_path).name for i in items])
                _cache[rd] = names
            except Exception:
                return False
        return name in names

    async def list_all_sub_paths(
        self, shared_path: str, uk: int, share_id: int, bdstoken: str, size=100
    ) -> List[PcsSharedPath]:
        """列出所有子路径"""

        sub_paths = []
        for page in range(1, 1000):
            sps = await self._list_shared_paths(shared_path, uk, share_id, bdstoken, page=page, size=size)
            sub_paths.extend(sps)
            if len(sps) < size:
                break
        return sub_paths

    async def get_relationship_list(
        self, params: RelationshipParam, **kwargs: Any
    ) -> Union[List[GetUserFriendDetail], List[GetUserGroupDetail], List[Any]]:
        """
        获取所有关注的用户列表或群组列表

        参数:
            params (RelationshipParam): 关系查询参数
            **kwargs: 其他关键字参数

        返回:
            Union[List[GetUserFriendDetail], List[GetUserGroupDetail]]: 用户/群组列表
        """
        relationship_type = params.relationship_type
        all_items = []
        start = 0
        limit = 20  # 百度API通常限制为20
        max_iterations = 100  # 防止无限循环的最大迭代次数
        iteration_count = 0

        if relationship_type not in [RelationshipType.FRIEND, RelationshipType.GROUP]:
            self.logger.error(f"无效的 relationship_type: {relationship_type}. 必须是 'friend' 或 'group'.")
            return []

        while iteration_count < max_iterations:
            iteration_count += 1
            response = None  # 初始化响应
            try:
                if relationship_type == RelationshipType.FRIEND:
                    response = await self._baidupcs.get_follow_list(start=start, limit=limit)
                elif relationship_type == RelationshipType.GROUP:
                    response = await self._baidupcs.get_group_list(start=start, limit=limit)
                else:  # 由于上面的检查，这种情况不应该发生
                    return []
            except BaiduApiError as e:
                self.logger.error(f'获取 {relationship_type} 列表时API出错: {e}')
                break
            except Exception as e:
                self.logger.error(f'获取 {relationship_type} 列表时发生未知错误: {e}')
                break

            if response is None:
                self.logger.error(f'获取 {relationship_type} 列表后响应为空，可能在API调用后出现意外情况。')
                break

            if response.get('errno') != 0:
                self.logger.error(f'获取 {relationship_type} 列表失败: {response}')
                break

            records = response.get('records', [])
            if not records:
                self.logger.debug(f'第 {iteration_count} 次迭代未获取到记录，结束循环')
                break

            # 记录本次获取的数量
            records_count = len(records)
            self.logger.debug(f'第 {iteration_count} 次迭代获取到 {records_count} 条记录')

            for record in records:
                if relationship_type == RelationshipType.FRIEND:
                    try:
                        # 映射API返回的好友数据到GetUserFriendDetail模型
                        friend_data = {
                            'uk': int(record.get('uk', 0)),
                            'uname': record.get('uname', ''),
                            'nick_name': record.get('nick_name', ''),
                            'avatar_url': record.get('avatar_url', ''),
                            'is_friend': record.get('is_friend', 2),
                        }
                        item = GetUserFriendDetail(**friend_data)
                    except Exception as e:
                        self.logger.error(f'解析好友数据失败: {record}, 错误: {e}')
                        continue
                elif relationship_type == RelationshipType.GROUP:
                    try:
                        # 映射API返回的群组数据到GetUserGroupDetail模型
                        group_data = {
                            'gid': str(record.get('gid', '')),
                            'gnum': str(record.get('gnum', '')),
                            'name': record.get('name', ''),
                            'type': str(record.get('type', '0')),
                            'status': str(record.get('status', '1')),
                        }
                        item = GetUserGroupDetail(**group_data)
                    except Exception as e:
                        self.logger.error(f'解析群组数据失败: {record}, 错误: {e}')
                        continue
                else:
                    self.logger.warning(f'未知的关系类型: {relationship_type}')
                    return []
                all_items.append(item)

            # 检查是否还有更多数据
            has_more = False
            if relationship_type == RelationshipType.FRIEND:
                has_more = response.get('has_more', False)
            elif relationship_type == RelationshipType.GROUP:
                total_count = response.get('count', 0)
                current_fetched = start + records_count
                has_more = current_fetched < total_count and response.get('has_more', True)

            # 如果没有更多数据或者本次获取的记录数少于限制数，则结束循环
            if not has_more or records_count < limit:
                self.logger.debug(f'结束循环: has_more={has_more}, records_count={records_count}, limit={limit}')
                break

            start += limit

        if iteration_count >= max_iterations:
            self.logger.warning(f'达到最大迭代次数 {max_iterations}，强制结束循环')

        # self.logger.info(f"获取 {relationship_type} 列表完成，共 {len(all_items)} 项，迭代 {iteration_count} 次")
        return all_items

    async def get_relationship_share_list(
        self, relationship_type: str, identifier: str, type: int = 2, **kwargs
    ) -> Dict:
        """获取好友或群组的分享列表

        Args:
            relationship_type (str): "friend" 或 "group"
            identifier (str): 当 relationship_type 为 "friend" 时, 此为好友的 UK (to_uk);
                              当 relationship_type 为 "group" 时, 此为群组的 ID (gid).
            type (int): 分享类型，API 默认为 2.
            **kwargs: 其他可选参数.
                对于群组类型 (relationship_type="group"):
                    limit (int): 每页数量，默认为 50.
                    desc (int): 是否降序 (1降序, 0升序)，默认为 1.
                其他参数 (如 clienttype, app_id, web) 会透传给底层 API.

        Returns:
            Dict: 返回分享列表信息
        """
        if relationship_type == 'friend':
            # 对于好友分享，limit 和 desc 不是 get_friend_share_list 的直接参数
            # 如果它们在 kwargs 中，会传递给底层 API，但可能被忽略
            return await self._baidupcs.get_friend_share_list(to_uk=identifier, type=type, **kwargs)
        elif relationship_type == 'group':
            # 从 kwargs 中提取群组特定的参数，如果未提供则使用默认值
            group_limit = kwargs.pop('limit', 50)
            group_desc = kwargs.pop('desc', 1)
            return await self._baidupcs.get_group_share_list(
                gid=identifier, type=type, limit=group_limit, desc=group_desc, **kwargs
            )
        else:
            self.logger.error(f"无效的 relationship_type: {relationship_type}. 必须是 'friend' 或 'group'.")
            return {'errno': -1, 'error_msg': f'无效的 relationship_type: {relationship_type}', 'records': []}

    async def get_relationship_share_detail(
        self,
        relationship_type: str,
        identifier: str,
        from_uk: str,
        msg_id: str,
        fs_id: str,
        page: int = 1,
        num: int = 50,
        **kwargs,
    ) -> Dict:
        """获取好友或群组的分享详情

        Args:
            relationship_type (str): "friend" 或 "group"
            identifier (str): 当 relationship_type 为 "friend" 时, 此为接收者的 UK (to_uk，即当前登录用户);
                              当 relationship_type 为 "group" 时, 此为群组的 ID (gid).
            from_uk (str): 分享者UK
            msg_id (str): 消息ID
            fs_id (str): 文件ID
            page (int): 页码，默认为1
            num (int): 每页数量，默认为50
            **kwargs: 其他可选参数.
                type (int): 分享类型. 如果未提供, 好友默认为1, 群组默认为2.
                对于群组类型 (relationship_type="group"):
                    limit (int): 列表限制，默认为 50.
                    desc (int): 是否降序 (1降序, 0升序)，默认为 1.
                其他参数 (如 clienttype, app_id, web) 会透传给底层 API.

        Returns:
            Dict: 返回分享详情信息
        """
        if relationship_type == 'friend':
            # 如果 'type' 在 kwargs 中，则使用它，否则默认为 1
            final_type = kwargs.pop('type', 1)

            # 确保有有效的用户ID
            current_user_id = self.user_id
            if current_user_id is None:
                # 如果没有用户ID，尝试获取
                user_info_response = await self._baidupcs.get_user_info()
                if isinstance(user_info_response, dict):
                    user_info = user_info_response.get('user_info', {})
                    if isinstance(user_info, dict):
                        current_user_id = int(user_info.get('uk')) if user_info.get('uk') is not None else None
                        if current_user_id:
                            self._baidupcs._user_id = current_user_id

            if current_user_id is None:
                self.logger.error('获取好友分享详情失败: 无法获取当前用户ID，请检查登录状态')
                return {'errno': -1, 'error_msg': '无法获取当前用户ID，请检查登录状态'}

            return await self._baidupcs.get_friend_share_detail(
                from_uk=from_uk,
                msg_id=msg_id,
                to_uk=str(current_user_id),  # 使用获取到的用户ID作为接收者
                fs_id=fs_id,
                type=final_type,
                page=page,
                num=num,
                **kwargs,  # 传递剩余的 kwargs
            )
        elif relationship_type == 'group':
            # 如果 'type' 在 kwargs 中，则使用它，否则默认为 2
            final_type = kwargs.pop('type', 2)
            # 从 kwargs 中提取群组特定的参数，如果未提供则使用 API 定义的默认值
            group_limit = kwargs.pop('limit', 50)
            group_desc = kwargs.pop('desc', 1)
            return await self._baidupcs.get_group_share_detail(
                from_uk=from_uk,
                msg_id=msg_id,
                gid=identifier,  # identifier 是 gid
                fs_id=fs_id,
                type=final_type,
                page=page,
                num=num,
                limit=group_limit,
                desc=group_desc,
                **kwargs,  # 传递剩余的 kwargs
            )
        else:
            self.logger.error(f"无效的 relationship_type: {relationship_type}. 必须是 'friend' 或 'group'.")
            return {'errno': -1, 'error_msg': f'无效的 relationship_type: {relationship_type}'}

    async def get_share_list(self, params: ListShareFilesParam, **kwargs: Any) -> List[BaseFileInfo]:
        """
        获取分享文件列表（单层，不递归）

        :param params: 分享文件列表参数
        :param kwargs: 其他参数
        :return: 文件信息列表
        """
        source_type = params.source_type
        source_id = params.source_id
        file_path = params.file_path

        drive_files_list: List[BaseFileInfo] = []

        # 链接类型（外部链接）
        if source_type == 'link':
            # 支持 "url|pwd" 的混合输入；否则从 kwargs 中读取 password（可选）
            link = source_id
            password = kwargs.get('password', '')
            if '|' in link:
                parts = link.split('|', 1)
                link, password = parts[0].strip(), parts[1].strip()
            else:
                # 从查询串中提取 pwd 参数（如 ?pwd=xxxx）
                try:
                    parsed = urlparse(link)
                    if not password and parsed.query:
                        q = parse_qs(parsed.query)
                        if 'pwd' in q and q['pwd']:
                            password = q['pwd'][0]
                except Exception:
                    pass

            # 规范化链接
            try:
                shared_url = _unify_shared_url(link)
            except Exception as e:
                self.logger.error(f'无效的分享链接: {link}, 错误: {e}')
                return []

            # 如果提供了密码或链接需要密码，则尝试访问（无验证码流程）
            if password:
                try:
                    await self._baidupcs.access_shared(shared_url, password, '', '')
                except BaiduApiError as e:
                    self.logger.error(f'访问加密分享链接失败或需要验证码（暂不支持验证码流程）: {e}')
                    return []

            # 根级列表
            try:
                root_items: List[PcsSharedPath] = await self._shared_paths(shared_url)
            except Exception as e:
                self.logger.error(f'读取分享根目录失败: {e}')
                return []

            # 如果 file_path 为根，直接返回根级
            normalized = (file_path or '/').strip('/')
            if not normalized:
                for sp in root_items:
                    base_name = PurePosixPath(sp.path).name
                    drive_files_list.append(
                        BaseFileInfo(
                            file_id=str(sp.fs_id),
                            file_name=base_name,
                            file_path=f'/{base_name}',
                            file_size=sp.size if hasattr(sp, 'size') else 0,
                            is_folder=not getattr(sp, 'is_file', False),
                            created_at=str(getattr(sp, 'server_ctime', '')),
                            updated_at=str(getattr(sp, 'server_mtime', '')),
                            parent_id='',
                            file_ext={
                                'uk': getattr(sp, 'uk', None),
                                'share_id': getattr(sp, 'share_id', None),
                                'bdstoken': getattr(sp, 'bdstoken', None),
                                'shorturl': _extract_shorturl_from_url(shared_url),
                                'path': sp.path,
                            },
                        )
                    )
                return drive_files_list

            # 否则逐级导航到指定路径
            # 提取共享上下文（uk, share_id, bdstoken）
            if not root_items:
                return []
            uk = getattr(root_items[0], 'uk', None)
            share_id = getattr(root_items[0], 'share_id', None)
            bdstoken = getattr(root_items[0], 'bdstoken', None)
            if uk is None or share_id is None or bdstoken is None:
                self.logger.error('无法解析分享上下文(uk/share_id/bdstoken)')
                return []

            async def list_children(dir_path: str) -> List[PcsSharedPath]:
                page = 1
                page_size = 100
                all_items: List[PcsSharedPath] = []
                while True:
                    try:
                        items = await self._list_shared_paths(
                            dir_path, int(uk), int(share_id), str(bdstoken), page=page, size=page_size
                        )
                    except Exception as err:
                        self.logger.error(f'获取子目录失败: {dir_path}: {err}')
                        break
                    all_items.extend(items)
                    if len(items) < page_size:
                        break
                    page += 1
                return all_items

            # 当前目录的列表（从根出发）
            current_dir_items = root_items
            current_dir_path = ''
            components = normalized.split('/')

            for idx, name in enumerate(components):
                # 在当前层查找目标项
                matched: Optional[PcsSharedPath] = None
                for sp in current_dir_items:
                    if PurePosixPath(sp.path).name == name:
                        matched = sp
                        break
                if not matched:
                    self.logger.error(f'路径组件不存在: {name}')
                    return []

                is_last = idx == len(components) - 1
                current_dir_path = matched.path
                if not getattr(matched, 'is_file', False):
                    # 是目录
                    if is_last:
                        # 列出该目录
                        children = await list_children(current_dir_path)
                        for child in children:
                            base_name = PurePosixPath(child.path).name
                            drive_files_list.append(
                                BaseFileInfo(
                                    file_id=str(child.fs_id),
                                    file_name=base_name,
                                    file_path=f'/{normalized}/{base_name}',
                                    file_size=child.size if hasattr(child, 'size') else 0,
                                    is_folder=not getattr(child, 'is_file', False),
                                    created_at=str(getattr(child, 'server_ctime', '')),
                                    updated_at=str(getattr(child, 'server_mtime', '')),
                                    parent_id=str(matched.fs_id),
                                    file_ext={
                                        'uk': uk,
                                        'share_id': share_id,
                                        'bdstoken': bdstoken,
                                        'shorturl': _extract_shorturl_from_url(shared_url),
                                        'path': child.path,
                                    },
                                )
                            )
                        return drive_files_list
                    # 不是最后一段，进入下一层
                    current_dir_items = await list_children(current_dir_path)
                else:
                    # 是文件
                    if not is_last:
                        self.logger.error(f"路径组件 '{name}' 是文件，但还有后续路径")
                        return []
                    # 目标就是该文件
                    base_name = PurePosixPath(matched.path).name
                    drive_files_list.append(
                        BaseFileInfo(
                            file_id=str(matched.fs_id),
                            file_name=base_name,
                            file_path=f'/{normalized}',
                            file_size=matched.size if hasattr(matched, 'size') else 0,
                            is_folder=False,
                            created_at=str(getattr(matched, 'server_ctime', '')),
                            updated_at=str(getattr(matched, 'server_mtime', '')),
                            parent_id=str(getattr(matched, 'parent_id', '')),
                            file_ext={
                                'uk': uk,
                                'share_id': share_id,
                                'bdstoken': bdstoken,
                                'shorturl': _extract_shorturl_from_url(shared_url),
                                'path': matched.path,
                            },
                        )
                    )
                    return drive_files_list

            return drive_files_list

        normalized_file_path = file_path.strip('/')
        if not normalized_file_path:
            # 当 file_path 为根路径 "/" 时，返回所有分享的根项目
            # 1. Get all share events/messages
            share_events_response = await self.get_relationship_share_list(
                relationship_type=source_type, identifier=source_id
            )

            if share_events_response.get('errno', 0) != 0:
                self.logger.error(f'Failed to get share events for {source_type} {source_id}: {share_events_response}')
                return []

            share_messages = []
            records_obj = share_events_response.get('records', {})
            if source_type == 'friend':
                share_messages = records_obj.get('list', [])
            elif source_type == 'group':
                share_messages = records_obj.get('msg_list', [])

            if not share_messages:
                return []

            # 2. 为每个分享事件创建根项目 BaseFileInfo
            for share_event in share_messages:
                msg_id = share_event.get('msg_id')
                sharer_uk = None
                share_root_items_list = []

                if source_type == 'friend':
                    sharer_uk = share_event.get('from_uk')
                    share_root_items_list = share_event.get('filelist', {}).get('list', [])
                elif source_type == 'group':
                    sharer_uk = share_event.get('uk')
                    share_root_items_list = share_event.get('file_list', [])  # 对于群组是直接的列表

                if not msg_id or sharer_uk is None or not share_root_items_list:
                    self.logger.debug(f'跳过分享事件，缺少必要信息 (msg_id, sharer_uk, 或根项目): {share_event}')
                    continue

                share_event_root_item = share_root_items_list[0]  # 假设第一个项目是主要的分享根
                root_item_name = share_event_root_item.get('server_filename')
                root_item_fs_id = share_event_root_item.get('fs_id')

                if not root_item_name or root_item_fs_id is None:
                    self.logger.debug(f'跳过分享事件的根项目，缺少名称/fs_id: {share_event_root_item}')
                    continue

                # 为根路径创建 BaseFileInfo
                root_drive_file = BaseFileInfo(
                    file_id=str(root_item_fs_id),
                    file_name=root_item_name,
                    file_path=f'/{root_item_name}',
                    file_size=share_event_root_item.get('size', 0),
                    is_folder=bool(share_event_root_item.get('isdir', 0)),
                    created_at=str(share_event_root_item.get('server_ctime', '')),
                    updated_at=str(share_event_root_item.get('server_mtime', '')),
                    parent_id='',  # 根项目没有父ID
                    file_ext={
                        'from_uk': str(sharer_uk),
                        'msg_id': str(msg_id),
                    },
                )

                drive_files_list.append(root_drive_file)

            return drive_files_list

        # 对于非根路径，解析路径组件
        path_components = normalized_file_path.split('/')

        # 1. Get all share events/messages
        share_events_response = await self.get_relationship_share_list(
            relationship_type=source_type, identifier=source_id
        )

        if share_events_response.get('errno', 0) != 0:
            self.logger.error(f'Failed to get share events for {source_type} {source_id}: {share_events_response}')
            return []

        share_messages = []
        records_obj = share_events_response.get('records', {})
        if source_type == 'friend':
            share_messages = records_obj.get('list', [])
        elif source_type == 'group':
            share_messages = records_obj.get('msg_list', [])

        if not share_messages:
            return []

        target_share_info = None

        for share_event in share_messages:
            msg_id = share_event.get('msg_id')
            sharer_uk = None
            share_root_items_list = []

            if source_type == 'friend':
                sharer_uk = share_event.get('from_uk')
                share_root_items_list = share_event.get('filelist', {}).get('list', [])
            elif source_type == 'group':
                sharer_uk = share_event.get('uk')
                share_root_items_list = share_event.get('file_list', [])  # 对于群组是直接的列表

            if not msg_id or sharer_uk is None or not share_root_items_list:
                self.logger.debug(f'跳过分享事件，缺少必要信息 (msg_id, sharer_uk, 或根项目): {share_event}')
                continue

            share_event_root_item = share_root_items_list[0]  # 假设第一个项目是主要的分享根
            root_item_name = share_event_root_item.get('server_filename')
            root_item_fs_id = share_event_root_item.get('fs_id')

            if not root_item_name or root_item_fs_id is None:
                self.logger.debug(f'跳过分享事件的根项目，缺少名称/fs_id: {share_event_root_item}')
                continue

            if path_components[0] == root_item_name:
                target_share_info = {
                    'msg_id': str(msg_id),
                    'sharer_uk': str(sharer_uk),
                    'root_fs_id': str(root_item_fs_id),
                    'root_name': str(root_item_name),
                }
                break  # 找到目标分享事件

        if not target_share_info:
            self.logger.warning(
                f"No share event found with root item named '{path_components[0]}' for {source_type} {source_id}."
            )
            return []

        # 定义分享文件分页获取函数
        async def fetch_all_share_pages_from_api(
            relationship_type: str, identifier: str, from_uk: str, msg_id: str, fs_id: str
        ) -> List[Dict]:
            """
            自动翻页获取分享文件列表的所有页面数据（单层）

            :param relationship_type: 关系类型 (friend/group)
            :param identifier: 标识符
            :param from_uk: 分享者UK
            :param msg_id: 消息ID
            :param fs_id: 文件系统ID
            :return: 所有页面的文件列表
            """
            page = 1
            page_size = 50
            all_items = []

            while True:
                try:
                    detail_response = await self.get_relationship_share_detail(
                        relationship_type=relationship_type,
                        identifier=identifier,
                        from_uk=from_uk,
                        msg_id=msg_id,
                        fs_id=fs_id,
                        page=page,
                        num=page_size,
                    )

                    if detail_response.get('errno') != 0:
                        self.logger.warning(f'获取第{page}页分享数据失败 fs_id: {fs_id}: {detail_response}')
                        break

                    current_items = detail_response.get('records', [])
                    all_items.extend(current_items)

                    # 检查是否还有更多数据
                    has_more = detail_response.get('has_more', 0)
                    if has_more == 0:  # 没有更多数据
                        break

                    page += 1
                except Exception as e:
                    self.logger.error(f'获取第{page}页分享数据失败 fs_id: {fs_id}: {e}')
                    break

            return all_items

        # 3. Navigate to the target path
        current_nav_fs_id = target_share_info['root_fs_id']
        current_constructed_drive_path = f'/{target_share_info["root_name"]}'

        for component_idx in range(1, len(path_components)):
            component_name = path_components[component_idx]
            self.logger.debug(f"Navigating: current_fs_id={current_nav_fs_id}, seeking component='{component_name}'")

            items_in_current_dir = await fetch_all_share_pages_from_api(
                relationship_type=source_type,
                identifier=source_id,
                from_uk=target_share_info['sharer_uk'],
                msg_id=target_share_info['msg_id'],
                fs_id=current_nav_fs_id,
            )
            found_next_component = False
            for item_dict in items_in_current_dir:
                item_name_api = item_dict.get('server_filename')
                if item_name_api == component_name:
                    if not item_dict.get('isdir') and component_idx < len(path_components) - 1:
                        self.logger.error(
                            f"Path component '{component_name}' is a file, but further path components exist in query."
                        )
                        return []
                    current_nav_fs_id = str(item_dict.get('fs_id'))
                    current_constructed_drive_path = current_constructed_drive_path + '/' + component_name
                    found_next_component = True
                    self.logger.debug(
                        f"Found path component '{component_name}', new current_nav_fs_id={current_nav_fs_id}, new_path_base={current_constructed_drive_path}"
                    )
                    break

            if not found_next_component:
                self.logger.error(
                    f"Path component '{component_name}' not found in directory (fs_id of parent: {(path_components[component_idx - 1] if component_idx > 0 else target_share_info['root_name'])})."
                )
                return []

        # 4. 获取目标路径的内容（单层）
        items_from_api = await fetch_all_share_pages_from_api(
            relationship_type=source_type,
            identifier=source_id,
            from_uk=target_share_info['sharer_uk'],
            msg_id=target_share_info['msg_id'],
            fs_id=current_nav_fs_id,
        )

        # 检查是否是单个文件
        is_listing_a_single_target_file = False
        if (
            len(items_from_api) == 1
            and str(items_from_api[0].get('fs_id')) == current_nav_fs_id
            and not items_from_api[0].get('isdir')
        ):
            is_listing_a_single_target_file = True
            self.logger.debug(f'列出的目标 fs_id {current_nav_fs_id} 是单个文件。')

        for item_dict in items_from_api:
            item_fs_id_str = str(item_dict.get('fs_id'))
            item_name = item_dict.get('server_filename', 'Unknown')
            is_folder_item = bool(item_dict.get('isdir'))

            # 构建 BaseFileInfo 路径
            drive_file_item_path_str = (
                current_constructed_drive_path
                if is_listing_a_single_target_file
                else f'{current_constructed_drive_path}/{item_name}'
            )

            df = BaseFileInfo(
                file_id=item_fs_id_str,
                file_name=item_name,
                file_path=drive_file_item_path_str,
                file_size=item_dict.get('size', 0),
                is_folder=is_folder_item,
                created_at=str(item_dict.get('server_ctime')),
                updated_at=str(item_dict.get('server_mtime')),
                parent_id=str(current_nav_fs_id),
                file_ext={
                    'from_uk': target_share_info['sharer_uk'],
                    'msg_id': target_share_info['msg_id'],
                },
            )

            drive_files_list.append(df)

        return drive_files_list

    async def get_share_info(
        self, params: ListShareInfoParam, **kwargs: Any
    ) -> Union[List[BaseShareInfo], Dict[str, Any]]:
        """
        获取分享信息详情

        :param params: 分享信息查询参数
        :param kwargs: 其他关键字参数
        :return: 分享信息列表或错误信息
        """
        source_type = params.source_type
        source_id = params.source_id
        page = params.page
        size = params.size
        order_field = params.order_field
        order_type = params.order_type

        try:
            if source_type == 'link':
                # 对于分享链接，source_id 就是分享链接
                shorturl = _extract_shorturl_from_url(source_id)

                # 调用API获取分享详情（@assert_ok装饰器已处理errno检查）
                info = await self._baidupcs.get_share_detail(
                    shorturl=shorturl,
                    page=page,
                    num=size,
                    order=order_field if order_field == 'time' else 'time',
                    desc=1 if order_type == 'desc' else 0,
                    **kwargs,
                )

                # 获取分享的基本信息
                share_id = str(info.get('share_id', ''))
                title = info.get('title', '')
                expired_type = info.get('expired_type', 0)

                # 处理分享中的文件列表（一定会有文件列表）
                file_list = info.get('list', [])
                share_info_list = []

                for file_item in file_list:
                    from datetime import datetime

                    # 计算过期时间
                    expired_at = None
                    if expired_type > 0:
                        # 使用服务器时间作为基准
                        server_time = info.get('server_time')
                        if server_time:
                            expired_at = datetime.fromtimestamp(
                                server_time + expired_type * 24 * 3600, tz=timezone.tz_info
                            )

                    share_info = BaseShareInfo(
                        title=title or file_item.get('server_filename', ''),
                        share_id=share_id,
                        pwd_id='',  # 百度网盘通过分享链接获取，没有pwd_id概念
                        url=source_id,  # 原始分享链接
                        password=file_item.get('passwd', ''),
                        expired_type=expired_type,
                        view_count=0,  # API没有返回浏览量信息
                        expired_at=expired_at,
                        expired_left=None,
                        audit_status=1,  # 假设通过审核
                        status=1,  # 假设正常状态
                        file_id=str(file_item.get('fs_id', '')),
                        file_only_num=None,
                        file_size=int(file_item.get('size', 0)) if file_item.get('size') else None,
                        path_info=file_item.get('path', ''),
                    )
                    share_info_list.append(share_info)

                return share_info_list

            elif source_type == 'local':
                # 对于本地分享（用户自己创建的分享），使用 get_share_page API
                info = await self._baidupcs.get_share_page(page=page, size=size)

                # 处理API返回的数据，转换为 BaseShareInfo 对象列表
                share_info_list = []

                if isinstance(info, dict) and 'list' in info:
                    list_data = info.get('list', [])

                    for share_item in list_data:
                        from datetime import datetime

                        # 解析过期时间和过期类型
                        expired_type = share_item.get('expiredType', 0)

                        # 解析过期时间
                        expired_at = None
                        if expired_type > 0:
                            # 使用创建时间 + 有效期计算过期时间
                            create_time = share_item.get('ctime')
                            if create_time:
                                expired_at = datetime.fromtimestamp(
                                    create_time + expired_type * 24 * 3600, tz=timezone.tz_info
                                )

                        # 构建 BaseShareInfo 对象
                        share_info = BaseShareInfo(
                            title=share_item.get('typicalPath', '') or share_item.get('title', ''),
                            share_id=str(share_item.get('shareId', '')),
                            pwd_id=str(share_item.get('shareId', '')),  # 使用 shareId 作为 pwd_id
                            url=share_item.get('shorturl', ''),
                            password=share_item.get('passwd', ''),
                            expired_type=expired_type,
                            view_count=int(share_item.get('viewCount', 0)),
                            expired_at=expired_at,
                            expired_left=None,  # 留空，不计算也不使用API返回值
                            audit_status=1,  # 假设通过审核
                            status=1 if expired_type != -1 else 0,  # 过期则状态为0
                            file_id=str(share_item.get('fileId', '')),
                            file_only_num=None,
                            file_size=int(share_item.get('fileSize', 0)) if share_item.get('fileSize') else None,
                            path_info=share_item.get('typicalPath', ''),
                        )
                        share_info_list.append(share_info)

                return share_info_list

            else:
                return {'errno': -1, 'error_msg': f'不支持的分享来源类型: {source_type}'}

        except BaiduApiError as e:
            if self._is_auth_error(e):
                raise DriveAuthError(str(e), drive_type=self.drive_type) from e
            self.logger.error(f'获取分享信息时发生百度API错误: {e}')
            return {'errno': -1, 'error_msg': f'API错误: {str(e)}'}
        except DriveAuthError:
            raise
        except Exception as e:
            if self._is_auth_error(e):
                raise DriveAuthError(str(e), drive_type=self.drive_type) from e
            self.logger.error(f'获取分享信息时发生未知错误: {e}')
            return {'errno': -1, 'error_msg': f'未知错误: {str(e)}'}

    async def transfer(self, params: TransferParam, **kwargs: Any) -> bool:
        """
        从各种来源传输文件到自己的网盘。

        参数:
            source_type (str): 来源类型，可选值："link" (链接分享), "group" (群组分享), "friend" (好友分享)。
            source_id (str): 来源的唯一标识符。
                             - 当 source_type 为 "link" 时, 此为分享链接的URL (当前未实现)。
                             - 当 source_type 为 "group" 时, 此为群组的ID (gid)。
                             - 当 source_type 为 "friend" 时, 此为好友的用户ID (UK)，即分享者。
            source_path (str): 源文件/目录在分享中的路径 (百度网盘在此转存场景下通常不直接使用此参数进行API调用，
                               而是依赖 file_ids, msg_id 以及分享者信息，但为保持接口兼容性而保留)。
            target_path (str): 文件/目录在用户自己网盘中保存的目标路径。
            file_ids (Optional[List[Union[int, str]]]): 要传输的文件/目录的 fs_id 列表。
                                                      对于 "friend" 和 "group" 类型的转存是必需的。
            **kwargs (Any): 其他可选参数。
                           - msg_id (str): 消息ID。对于 "friend" 和 "group" 类型的转存是必需的。
                           - from_uk (str): 分享者的用户ID (UK)。当 source_type 为 "group" 时是必需的 (因为此时 source_id 是群组ID)。
                           - ondup (str): 文件名冲突时的处理方式，可选值为 "newcopy" (新建副本，默认), "skip" (跳过)。
                           - async (int): 是否异步执行，可传递给底层API (例如 0 或 1，默认为1，表示异步)。

        返回:
            bool: 如果转存操作被API接受并报告成功，则返回 True；否则返回 False。
        """
        source_type = params.source_type
        source_id = params.source_id
        target_path = params.target_path
        file_ids = params.file_ids

        # 合并 params.ext 和 kwargs，params.ext 中的参数优先级更高
        combined_kwargs = {}
        combined_kwargs.update(kwargs)
        if params.ext:
            combined_kwargs.update(params.ext)

        # 确保target_path使用正斜杠
        target_path = target_path.replace('\\', '/')

        # self.logger.info(
        #     f"转存请求: source_type='{source_type}', source_id='{source_id}', "
        #     f"source_path='{source_path}', target_path='{target_path}', file_ids='{file_ids}'"
        # )

        # 确保用户ID可用
        current_user_id = self.user_id
        if current_user_id is None:
            # 如果没有用户ID，尝试获取
            user_info_response = await self._baidupcs.get_user_info()
            if isinstance(user_info_response, dict):
                user_info = user_info_response.get('user_info', {})
                if isinstance(user_info, dict):
                    current_user_id = int(user_info.get('uk')) if user_info.get('uk') is not None else None
                    if current_user_id:
                        self._baidupcs._user_id = current_user_id

        if not current_user_id:
            self.logger.error('转存失败: 无法获取用户ID，请检查登录状态')
            return False

        if source_type == 'link':
            # 直接在此内联原 save_shared 逻辑，避免额外方法
            shared_url = _unify_shared_url(source_id)

            # 若提供密码则访问授权；公开分享可跳过
            password = combined_kwargs.get('password', '')
            if password:
                try:
                    await self._baidupcs.access_shared(shared_url, password, '', '')
                except BaiduApiError as err:
                    self.logger.error(f'保存共享失败: 访问加密分享需要验证码或密码错误: {err}')
                    return False

            shared_paths_list = await self._shared_paths(shared_url)
            if not shared_paths_list:
                return False

            shared_paths_deque = deque(shared_paths_list)
            remote_dir = target_path
            _remote_dirs: Dict[PcsSharedPath, str] = dict([(sp, remote_dir) for sp in shared_paths_deque])
            _dir_exists: Set[str] = set()

            while shared_paths_deque:
                shared_path = shared_paths_deque.popleft()
                rd = _remote_dirs[shared_path]

                if rd not in _dir_exists:
                    if not await self.exists(rd):
                        await self.mkdir(MkdirParam(drive_type=self.drive_type, file_path=rd))
                    _dir_exists.add(rd)

                if shared_path.is_file and await self.remote_path_exists(PurePosixPath(shared_path.path).name, rd):
                    self.logger.warning(f'{shared_path.path} has be in {rd}')
                    continue

                uk, share_id_val, bdstoken_val = (
                    shared_path.uk,
                    shared_path.share_id,
                    shared_path.bdstoken,
                )

                try:
                    await self._transfer_shared_paths(
                        rd, [shared_path.fs_id], uk, share_id_val, bdstoken_val, shared_url
                    )
                    continue
                except BaiduApiError as err:
                    if err.error_code == 12:
                        self.logger.warning(
                            f'error_code: {err.error_code}, 文件已经存在, {shared_path.path} has be in {rd}'
                        )
                    elif err.error_code == -32:
                        self.logger.error(f'error_code:{err.error_code} 剩余空间不足，无法转存')
                    elif err.error_code == -33:
                        self.logger.error(f'error_code:{err.error_code} 一次支持操作999个，减点试试吧')
                    elif err.error_code == 4:
                        self.logger.error(f'error_code:{err.error_code} share transfer pcs error')
                    elif err.error_code in (120, 130):
                        self.logger.error(f'error_code:{err.error_code} 转存文件数超限')
                    else:
                        self.logger.error(f'转存 {shared_path.path} 失败: error_code:{err.error_code}:{err}')
                        continue

                if shared_path.is_dir:
                    sub_paths = await self.list_all_sub_paths(shared_path.path, uk, share_id_val, bdstoken_val)
                    current_dir_name = PurePosixPath(shared_path.path).name
                    sub_remote_dir = (Path(rd) / current_dir_name).as_posix()
                    for sp in sub_paths:
                        _remote_dirs[sp] = sub_remote_dir
                    shared_paths_deque.extendleft(sub_paths[::-1])

            return True

        elif source_type in ['friend', 'group']:
            if not file_ids:
                self.logger.error(f"转存失败: source_type '{source_type}' 需要 'file_ids'.")
                return False

            msg_id = combined_kwargs.get('msg_id')
            if not msg_id:
                self.logger.error(f"转存失败: source_type '{source_type}' 的参数中需要 'msg_id'.")
                return False

            transfer_type = 1 if source_type == 'friend' else 2

            # 构建API参数
            api_kwargs = {
                'path': target_path,
                'ondup': combined_kwargs.get('ondup', 'newcopy'),
            }

            # 处理异步参数 - 简化逻辑
            async_value = combined_kwargs.get('async_', combined_kwargs.get('async', 1))
            api_kwargs['async_'] = int(async_value) if async_value is not None else 1

            from_uk_param = None

            if source_type == 'friend':
                from_uk_param = source_id  # source_id 是好友的 UK (分享者 UK)
            elif source_type == 'group':
                # source_id 是群组的 ID (gid)
                # api.py 中的 `transfer_files` 方法需要 `from_uk` (分享者) 和 `gid` (群组)
                from_uk_param = combined_kwargs.get('from_uk')  # 参数中必须提供分享者的 UK
                if not from_uk_param:
                    self.logger.error("群组分享转存失败: 参数中需要 'from_uk' (分享者 UK).")
                    return False
                api_kwargs['gid'] = source_id  # 将 gid 传递给 transfer_files 的 api_kwargs

            try:
                result = await self._baidupcs.transfer_files(
                    from_uk=str(from_uk_param) if from_uk_param else '',
                    to_uk=str(current_user_id),
                    msg_id=str(msg_id),
                    fs_ids=file_ids,
                    type=transfer_type,
                    **api_kwargs,
                )
                if result.get('errno') == 0:
                    # self.logger.info(f"source_type '{source_type}' 转存成功. API 响应: {result}")
                    return True
                else:
                    self.logger.error(f"source_type '{source_type}' 转存失败. API 响应: {result}")
                    return False
            except BaiduApiError as e:
                self.logger.error(f"'{source_type}' 转存期间发生百度 API 错误: {e}")
                return False
            except Exception as e:
                self.logger.error(f"'{source_type}' 转存期间发生意外错误: {e}")
                return False
        else:
            self.logger.error(f'不支持的转存 source_type: {source_type}')
            return False

    async def cancel_share(self, params: 'CancelShareParam', **kwargs: Any) -> bool:
        """
        取消分享链接

        :param params: 取消分享参数
        :param kwargs: 其他关键字参数
        :return: 是否成功取消
        """

        try:
            # 将字符串ID转换为整数
            share_ids = [int(sid) for sid in params.shareid_list]
            await self._baidupcs.cancel_shared(*share_ids)
            return True
        except DriveAuthError:
            raise
        except Exception as e:
            if self._is_auth_error(e):
                raise DriveAuthError(str(e), drive_type=self.drive_type) from e
            self.logger.error(f'取消分享时发生错误: {e}')
            return False
