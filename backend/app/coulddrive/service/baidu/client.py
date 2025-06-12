#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created On: 2023-01-01
@Author: PanMaster团队
百度网盘客户端实现
"""

from __future__ import annotations
import os
from collections import deque
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import IO, Callable, Dict, List, Optional, Set, Tuple, Union, Any
import re
from datetime import datetime
import time
import logging  # 导入标准日志模块
import asyncio

from PIL import Image

from backend.app.coulddrive.schema.enum import RecursionSpeed
from backend.app.coulddrive.schema.file import BaseFileInfo, ListFilesParam, ListShareFilesParam, MkdirParam, RemoveParam, TransferParam, RelationshipParam, RelationshipType, UserInfoParam
from backend.app.coulddrive.schema.user import (
    BaseUserInfo,
    GetUserFriendDetail,
    GetUserGroupDetail,
)

from backend.app.coulddrive.service.baidu.errors import BaiduApiError
from backend.app.coulddrive.service.filesync_service import ItemFilter
from backend.app.coulddrive.service.yp_service import BaseDriveClient
from .schemas import (
    FromTo,
    PcsFile,
    PcsQuota,
    PcsSharedLink,
    PcsSharedPath,
)
from backend.app.coulddrive.service.baidu.api import BaiduApi
from backend.common.log import log

SHARED_URL_PREFIX = "https://pan.baidu.com/s/"


def _unify_shared_url(url: str) -> str:
    """统一输入的分享链接格式"""

    # 标准链接格式
    temp = r"pan\.baidu\.com/s/(.+?)(\?|$)"
    m = re.search(temp, url)
    if m:
        return SHARED_URL_PREFIX + m.group(1)

    # surl 链接格式
    temp = r"baidu\.com.+?\?surl=(.+?)(\?|$)"
    m = re.search(temp, url)
    if m:
        return SHARED_URL_PREFIX + "1" + m.group(1)

    raise ValueError(f"The shared url is not a valid url. {url}")


class BaiduClient(BaseDriveClient):
    """百度网盘 PCS API

    这是对`BaiduPCS`的封装。它将原始BaiduPCS请求的响应内容解析为一些内部数据结构。
    """

    def __init__(
        self,
        cookies: str,
        user_id: Optional[int] = None,
    ):
        """
        
        :param cookies: cookies 字符串，格式如 "BDUSS=xxx; STOKEN=xxx; PTOKEN=xxx"
        :param user_id: 用户ID
        """
        super().__init__()
        # 初始化日志记录器
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 不要先创建空的 BaiduApi 实例，直接在 login 中创建
        self._baidupcs: BaiduApi = None
        self._is_authorized = False

        # 自动登录
        if self.login(cookies, user_id):
            pass
        else:
            raise ValueError("BaiduClient 初始化失败：登录失败")

    @property
    def drive_type(self) -> str:
        return "BaiduDrive"

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
                                user_info = user_info_response.get("user_info", {})
                                if isinstance(user_info, dict):
                                    user_id = int(user_info.get("uk")) if user_info.get("uk") is not None else None
                                    if user_id:
                                        self._baidupcs._user_id = user_id
                                        return True
                            return False
                        
                        # 尝试在当前上下文中运行验证
                        try:
                            loop = asyncio.get_running_loop()
                            # 在异步上下文中，暂时标记为已授权，用户ID稍后获取
                            self._is_authorized = True
                            return True
                        except RuntimeError:
                            # 在同步上下文中，立即验证登录
                            login_verified = asyncio.run(verify_login())
                            self._is_authorized = login_verified
                            return login_verified
                            
                    except Exception as e:
                        self.logger.debug(f"登录验证失败: {e}")
                        self._is_authorized = False
                        return False
                
                self._is_authorized = False
                return False
            except Exception as e:
                self.logger.error(f"BaiduApi 初始化失败: {e}")
                self._is_authorized = False
                return False
        
        # 如果没有认证信息且_baidupcs为None，返回False
        if self._baidupcs is None:
            self._is_authorized = False
            return False
            
        return self._is_authorized

    @property
    def bduss(self) -> str:
        return self._baidupcs._bduss if self._baidupcs else ""

    @property
    def bdstoken(self) -> str:
        return self._baidupcs.bdstoken if self._baidupcs else ""

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
        return PcsQuota(quota=info["quota"], used=info["used"])

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
                    is_supervip=bool(user_info.get('is_svip', 0))
                )
            else:
                error_msg = user_info_response.get('error_msg', '未知错误') if isinstance(user_info_response, dict) else str(user_info_response)
                self.logger.error(f"获取用户信息失败: {error_msg}")
                return BaseUserInfo(user_id='0', username='未知用户', avatar_url='', is_vip=False, is_supervip=False)
        except Exception as e:
            self.logger.error(f"获取用户信息时发生错误: {e}")
            return BaseUserInfo(user_id='0', username='未知用户', avatar_url='', is_vip=False, is_supervip=False)

    async def meta(self, *file_paths: str) -> List[PcsFile]:
        """获取`file_paths`的元数据"""

        info = await self._baidupcs.meta(*file_paths)
        return [PcsFile.from_(v) for v in info.get("list", [])]

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
        获取目录下的文件和目录列表
        
        :param params: 文件列表查询参数
        :param kwargs: 其他关键字参数
        """
        # 从 params 中提取参数
        file_path = params.file_path or "/"
        file_id = params.file_id or ""
        recursive = params.recursive
        desc = params.desc
        name = params.name
        time = params.time
        size = params.size_sort
        recursion_speed = params.recursion_speed
        
        # 确保路径格式正确
        if not file_path.startswith("/"):
            file_path = "/" + file_path
        
        # 从 kwargs 中获取可选参数
        item_filter = kwargs.get('item_filter', None)
        drive_account_id = kwargs.get('drive_account_id', None)
        db = kwargs.get('db', None)

        # 快速模式：优先从缓存获取
        if recursion_speed == RecursionSpeed.FAST and drive_account_id and db:
            try:
                from backend.app.coulddrive.service.file_cache_service import file_cache_service
                
                # 检查缓存新鲜度
                cache_fresh = await file_cache_service.check_cache_freshness(
                    db, drive_account_id=drive_account_id, parent_id=file_id or file_path
                )
                
                if cache_fresh:
                    self.logger.info(f"快速模式：从缓存获取文件列表 {file_path}")
                    cached_files = await file_cache_service.get_cached_children_as_file_info(
                        db, parent_id=file_id or file_path, drive_account_id=drive_account_id
                    )
                    
                    # 应用过滤器
                    if item_filter:
                        cached_files = [item for item in cached_files if not item_filter.should_exclude(item)]
                    
                    return cached_files
                else:
                    self.logger.info(f"快速模式：缓存过期，回退到API获取 {file_path}")
            except Exception as e:
                self.logger.warning(f"快速模式缓存获取失败，回退到API获取: {e}")

        drive_files_list: List[BaseFileInfo] = []
        initial_parent_id = file_id

        try:
            info = await self._baidupcs.list(
                file_path, desc=desc, name=name, time=time, size=size
            )
            initial_items_raw = info.get("list", [])
        except Exception as e:
            self.logger.error(f"Error listing path '{file_path}': {e}") # Added more context to log
            return []

        items_to_process = deque()
        # 将初始项目转换为 BaseFileInfo 以便进行早期过滤
        for item_dict_initial in initial_items_raw:
            # 创建用于过滤检查的初步 BaseFileInfo，这些顶级项目的 parent_id 是 initial_parent_id
            # 如果 file_path 本身指向一个文件，需要小心处理。get_disk_list 通常列出目录。
            # 目前假设如果 file_path 指向文件，initial_items_raw 将包含该文件。
            temp_df_for_filter = BaseFileInfo(
                file_id=str(item_dict_initial.get('fs_id', '')),
                file_path=item_dict_initial.get('path', ''),
                file_name=item_dict_initial.get('server_filename', ''),
                is_folder=bool(item_dict_initial.get('isdir', 0)),
                # 其他字段可以是虚拟的或最小的，用于过滤目的（如果过滤规则不使用）
                file_size=item_dict_initial.get('size'),
                created_at=str(item_dict_initial.get('server_ctime', '')),
                updated_at=str(item_dict_initial.get('server_mtime', '')),
                parent_id=str(initial_parent_id) if initial_parent_id is not None else ""
            )
            if item_filter and item_filter.should_exclude(temp_df_for_filter):
                self.logger.info(f"[Filter] 排除初始磁盘文件: {temp_df_for_filter.file_path}")
                continue
            items_to_process.append((item_dict_initial, initial_parent_id))
        
        # items_to_process = deque([(item_dict, initial_parent_id) for item_dict in initial_items_raw])
        all_processed_data = []
        processed_fs_ids = set()

        # 处理队列中的每个项目
        while items_to_process:
            item_dict, current_parent_id = items_to_process.popleft()
            
            # 在处理任何逻辑之前，先检查该项目是否应该被排除
            temp_file_info = BaseFileInfo(
                file_id=str(item_dict.get('fs_id', '')),
                file_path=item_dict.get('path', ''),
                file_name=item_dict.get('server_filename', ''),
                is_folder=bool(item_dict.get('isdir', 0)),
                file_size=item_dict.get('size'),
                created_at=str(item_dict.get('server_ctime', '')),
                updated_at=str(item_dict.get('server_mtime', '')),
                parent_id=str(current_parent_id) if current_parent_id is not None else ""
            )
            
            # 如果该项目被排除规则匹配，直接跳过，不添加到结果中，也不递归进入
            if item_filter and item_filter.should_exclude(temp_file_info):
                continue
            
            # 项目没有被排除，添加到结果数据中
            all_processed_data.append((item_dict, current_parent_id))

            current_fs_id = item_dict.get('fs_id')
            is_dir = bool(item_dict.get('isdir'))
            current_item_path = item_dict.get('path')

            # 如果是目录且需要递归，则获取子目录内容
            if is_dir and recursive and current_fs_id and current_fs_id not in processed_fs_ids:
                if current_item_path:
                    processed_fs_ids.add(current_fs_id)
                    if recursion_speed == RecursionSpeed.FAST:
                        # 快速模式：尝试从缓存获取子目录内容
                        if drive_account_id and db:
                            try:
                                from backend.app.coulddrive.service.file_cache_service import file_cache_service
                                
                                cached_children = await file_cache_service.get_cached_children_as_file_info(
                                    db, parent_id=str(current_fs_id), drive_account_id=drive_account_id
                                )
                                
                                if cached_children:
                                    self.logger.debug(f"快速模式：从缓存获取子目录 {current_item_path}")
                                    # 将缓存的子项添加到处理队列（注意：这里不再预先应用过滤器，让主循环处理）
                                    for cached_child in cached_children:
                                        child_dict = {
                                            'fs_id': int(cached_child.file_id) if cached_child.file_id.isdigit() else cached_child.file_id,
                                            'path': cached_child.file_path,
                                            'server_filename': cached_child.file_name,
                                            'size': cached_child.file_size,
                                            'isdir': 1 if cached_child.is_folder else 0,
                                            'server_ctime': cached_child.created_at,
                                            'server_mtime': cached_child.updated_at
                                        }
                                        items_to_process.append((child_dict, current_fs_id))
                                    continue
                                else:
                                    self.logger.debug(f"快速模式：缓存中无子目录数据，回退到API获取 {current_item_path}")
                            except Exception as e:
                                self.logger.warning(f"快速模式缓存获取失败，回退到API: {e}")
                        else:
                            self.logger.debug(f"快速模式：缺少必要参数，跳过子目录递归 {current_item_path}")
                            continue
                    elif recursion_speed == RecursionSpeed.SLOW:
                        self.logger.debug(f"Slow mode (disk): Pausing for 3s before listing {current_item_path}...")
                        time.sleep(3)
                
                    try:
                        sub_info = await self._baidupcs.list(
                            current_item_path, desc=desc, name=name, time=time, size=size
                        )
                        sub_list = sub_info.get("list", [])
                        # 将子项目添加到处理队列（让主循环统一处理排除规则）
                        for sub_item_dict in sub_list:
                            items_to_process.append((sub_item_dict, current_fs_id))
                    except Exception as e:
                        self.logger.error(f"Error listing subdirectory '{current_item_path}': {e}")
                        # 允许流程继续，如果子目录失败

        explicit_raw_keys = {
            "fs_id", "path", "server_filename", "size", "isdir", 
            "server_ctime", "server_mtime"
        }
        
        for item_dict, parent_id_for_item in all_processed_data:
            file_ext_val = {
                k: v for k, v in item_dict.items() if k not in explicit_raw_keys
            }

            file_instance = BaseFileInfo(
                file_id=str(item_dict.get('fs_id', '')),
                file_path=item_dict.get('path', ''),
                file_name=item_dict.get('server_filename', ''),
                file_size=item_dict.get('size'),
                is_folder=bool(item_dict.get('isdir', 0)),
                created_at=str(item_dict.get('server_ctime', '')), 
                updated_at=str(item_dict.get('server_mtime', '')), 
                parent_id=str(parent_id_for_item) if parent_id_for_item is not None else "",
                #file_ext=file_ext_val,
            )
            
            # 不再需要重复的过滤器检查，因为在主循环中已经处理了
            drive_files_list.append(file_instance)
        
        # 智能缓存写入：在获取文件列表后自动写入缓存
        if drive_account_id and db and drive_files_list:
            try:
                from backend.app.coulddrive.service.file_cache_service import file_cache_service
                
                cache_version = datetime.now().strftime("%Y%m%d_%H%M%S")
                await file_cache_service.smart_cache_write(
                    db, 
                    drive_account_id=drive_account_id,
                    files=drive_files_list,
                    cache_version=cache_version
                )
                self.logger.info(f"自动缓存写入完成: {len(drive_files_list)} 个文件")
            except Exception as e:
                self.logger.warning(f"自动缓存写入失败: {e}")
        
        return drive_files_list

    def search(
        self, keyword: str, file_path: str, recursive: bool = False
    ) -> List[PcsFile]:
        """在`file_path`中搜索`keyword`"""

        info = self._baidupcs.search(keyword, file_path, recursive=recursive)
        pcs_files = []
        for file_info in info["list"]:
            pcs_files.append(PcsFile.from_(file_info))
        return pcs_files

    async def mkdir(self,params: MkdirParam,**kwargs: Any) -> BaseFileInfo:
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
        file_name = params.file_name
        return_if_exist = params.return_if_exist

        # 规范化路径
        if not file_path.startswith("/"):
            file_path = "/" + file_path

        # 百度网盘使用完整路径创建目录，不需要额外拼接 file_name
        # file_path 已经是完整的目标路径，如 "/同步测试/四六级说明"
        # 不应该再拼接 file_name，否则会变成 "/同步测试/四六级说明/四六级说明"

        try:
            # 检查目录是否已存在
            if return_if_exist and await self.exists(file_path):
                # 获取已存在目录的信息
                meta_info = self.meta(file_path)
                if meta_info and len(meta_info) > 0:
                    pcs_file = meta_info[0]
                    return BaseFileInfo(
                        file_id=str(pcs_file.fs_id),
                        file_path=pcs_file.path,
                        file_name=os.path.basename(pcs_file.path),
                        is_folder=True,
                        file_size=0,
                        created_at=str(pcs_file.server_ctime) if pcs_file.server_ctime else "",
                        updated_at=str(pcs_file.server_mtime) if pcs_file.server_mtime else "",
                        parent_id=parent_id if parent_id else str(os.path.dirname(pcs_file.path))
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
                created_at=str(pcs_file.server_ctime) if pcs_file.server_ctime else "",
                updated_at=str(pcs_file.server_mtime) if pcs_file.server_mtime else "",
                parent_id=parent_id if parent_id else str(os.path.dirname(pcs_file.path))
            )

        except BaiduApiError as e:
            self.logger.error(f"创建目录失败: {e}")
            raise

    async def move(self, *file_paths: str) -> List[FromTo]:
        """将`file_paths[:-1]`移动到`file_paths[-1]`"""

        info = self._baidupcs.move(*file_paths)
        r = info["extra"].get("list")
        if not r:
            raise BaiduApiError("File operator [move] fails")
        return [FromTo(from_=v["from"], to_=v["to"]) for v in r]

    async def rename(self, source: str, dest: str) -> FromTo:
        """重命名文件"""
        
        info = self._baidupcs.rename(source, dest)
        r = info["extra"].get("list")
        if not r:
            raise BaiduApiError("File operator [rename] fails")
        v = r[0]
        return FromTo(from_=v["from"], to_=v["to"])

    async def copy(self, *file_paths: str):
        """将`file_paths[:-1]`复制到`file_paths[-1]`"""

        info = self._baidupcs.copy(*file_paths)
        r = info["extra"].get("list")
        if not r:
            raise BaiduApiError("File operator [copy] fails")
        return [FromTo(from_=v["from"], to_=v["to"]) for v in r]

    async def remove(
        self,
        params: RemoveParam,
        **kwargs: Any,
    ) -> bool:
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
                    if not path: continue # 跳过空路径
                    
                    current_path_to_delete = path
                    if not current_path_to_delete.startswith("/"):
                        current_path_to_delete = "/" + current_path_to_delete
                    paths_for_api_call.append(current_path_to_delete)
            
            elif file_ids and not input_paths_list:
                 self.logger.error(
                     "BaiduClient.remove 不支持单独使用 file_ids 删除，除非实现可靠的ID到路径转换或百度提供基于ID的删除API。"
                     "请同时提供对应的 file_paths。"
                 )
                 return False
            elif not input_paths_list and not file_ids:
                self.logger.warning("没有提供 file_paths 或 file_ids 进行删除操作。")
                return False # 或者 True，因为没有操作也算成功？

            if not paths_for_api_call:
                self.logger.info("处理输入后，没有可供删除的有效路径。")
                # 如果初始输入非空但最终没有可操作路径（例如，所有路径都不存在并被跳过），
                # 返回True表示操作完成且无错误，或False表示未达到预期删除效果。
                # 此处返回True表示"尝试删除，但没有符合条件的目标"。
                return True

            # 使用收集到的所有有效路径，一次性调用底层API
            await self._baidupcs.remove(*paths_for_api_call) 
            self.logger.info(f"已成功请求删除以下路径: {paths_for_api_call}")
            if file_ids: # 如果也提供了ID，可以一起记录，方便追踪
                 self.logger.debug(f"对应的 file_ids (如果提供): {file_ids}")

            return True
        
        except BaiduApiError as e:
            # 此处捕获由 _baidupcs.remove 或其他百度API调用（如 self.exists）抛出的 BaiduApiError
            msg = e.message if hasattr(e, 'message') and e.message else str(e)
            self.logger.error(f"删除文件/目录时发生百度API错误: {msg}")
            raise # 将 BaiduApiError 重新抛出，由上层 (server.py) 处理
        except Exception as e_generic:
            # 捕获其他未预料的错误
            self.logger.error(f"删除文件/目录时发生未知错误: {str(e_generic)}")
            # 将未知错误包装成 BaiduApiError 再抛出
            raise BaiduApiError(f"删除文件/目录失败 (未知错误): {str(e_generic)}")

    def share(self, *file_paths: str, password: str, period: int = 0) -> PcsSharedLink:
        """将`file_paths`公开分享，可选择使用密码

        要使用此API，`cookies`中必须包含`STOKEN`

        period (int): 过期天数。`0`表示永不过期
        """

        info = self._baidupcs.share(*file_paths, password=password, period=period)
        link = PcsSharedLink.from_(info)._replace(
            paths=list(file_paths), password=password
        )
        return link

    def list_shared(self, page: int = 1) -> List[PcsSharedLink]:
        """列出某页的分享链接

        要使用此API，`cookies`中必须包含`STOKEN`
        """

        info = self._baidupcs.list_shared(page)
        return [PcsSharedLink.from_(v) for v in info["list"]]

    def shared_password(self, share_id: int) -> Optional[str]:
        """显示分享链接密码

        要使用此API，`cookies`中必须包含`STOKEN`
        """

        info = self._baidupcs.shared_password(share_id)
        p = info.get("pwd", "0")
        if p == "0":
            return None
        return p

    def cancel_shared(self, *share_ids: int):
        """取消具有`share_ids`的分享链接

        要使用此API，`cookies`中必须包含`STOKEN`
        """

        self._baidupcs.cancel_shared(*share_ids)

    def access_shared(
        self,
        shared_url: str,
        password: str,
        vcode_str: Optional[str] = None,
        vcode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """验证需要`password`的`shared_url`
        如果需要验证码，将返回包含验证码信息的字典。
        否则，返回成功或失败的信息。
        """
        try:
            self._baidupcs.access_shared(shared_url, password, vcode_str or "", vcode or "") 
            return {"vcode_required": False, "success": True, "message": "访问共享链接成功"}
        except BaiduApiError as err:
            if err.error_code in (-9, -62):
                self.logger.warning(f"验证码相关错误: {err.error_code} - {err.message}")
                try:
                    vcode_challenge_str, vcode_img_url = self.getcaptcha(shared_url)
                    return {
                        "vcode_required": True,
                        "vcode_str": vcode_challenge_str,
                        "vcode_image_url": vcode_img_url,
                        "message": err.message or ("验证码错误或需要输入验证码" if err.error_code == -9 else "需要输入验证码"),
                        "original_error_code": err.error_code
                    }
                except BaiduApiError as captcha_err:
                    self.logger.error(f"获取验证码失败: {captcha_err}")
                    raise BaiduApiError(
                        message=f"访问共享链接时需要验证码，但获取新验证码失败: {captcha_err.message}", 
                        error_code=err.error_code,
                        cause=captcha_err
                    ) 
            else:
                self.logger.error(f"访问共享时发生其他错误: {err}")
                raise err

    def getcaptcha(self, shared_url: str) -> Tuple[str, str]:
        """获取一个验证码信息
        返回 `vcode_str`, `vcode_img_url`"""

        info = self._baidupcs.getcaptcha(shared_url)
        return info["vcode_str"], info["vcode_img"]

    def get_vcode_img(self, vcode_img_url: str, shared_url: str) -> bytes:
        """获取验证码图像内容"""

        return self._baidupcs.get_vcode_img(vcode_img_url, shared_url)

    def shared_paths(self, shared_url: str) -> List[PcsSharedPath]:
        """获取`shared_url`的共享路径"""

        info = self._baidupcs.shared_paths(shared_url)
        uk = info.get("share_uk") or info.get("uk")
        uk = int(uk)

        assert uk, "`BaiduPCSApi.shared_paths`: Don't get `uk`"

        share_id = info["shareid"]
        bdstoken = info["bdstoken"]

        if not info.get("file_list"):
            return []

        if isinstance(info["file_list"], list):
            file_list = info["file_list"]
        elif isinstance(info["file_list"].get("list"), list):
            file_list = info["file_list"]["list"]
        else:
            raise ValueError("`shared_paths`: Parsing shared info fails")

        return [
            PcsSharedPath.from_(v)._replace(uk=uk, share_id=share_id, bdstoken=bdstoken)
            for v in file_list
        ]

    async def list_shared_paths(
        self,
        sharedpath: str,
        uk: int,
        share_id: int,
        bdstoken: str,
        page: int = 1,
        size: int = 100,
    ) -> List[PcsSharedPath]:
        """共享目录`sharedpath`的子共享路径"""

        info = self._baidupcs.list_shared_paths(
            sharedpath, uk, share_id, page=page, size=size
        )
        return [
            PcsSharedPath.from_(v)._replace(uk=uk, share_id=share_id, bdstoken=bdstoken)
            for v in info["list"]
        ]

    async def transfer_shared_paths(
        self,
        remotedir: str,
        fs_ids: List[int],
        uk: int,
        share_id: int,
        bdstoken: str,
        shared_url: str,
    ):
        """保存这些共享路径的`fs_ids`到`remotedir`"""

        self._baidupcs.transfer_shared_paths(
            remotedir, fs_ids, uk, share_id, bdstoken, shared_url
        )

    async def save_shared(
        self, shared_url: str, remote_dir: str, password: Optional[str] = None
    ):
        """保存共享链接到指定目录"""
        
        shared_url = _unify_shared_url(shared_url)

        access_result = self.access_shared(shared_url, password or "") 
        if password:
            access_result = self.access_shared(shared_url, password, vcode_str=None, vcode=None)
            if access_result.get("vcode_required"):
                self.logger.error(f"保存共享失败: 需要验证码才能继续. {access_result}")
                raise BaiduApiError(message=f"需要验证码才能保存共享: {access_result.get('message')}", error_code=access_result.get('original_error_code', -62))
        
        shared_paths_list = self.shared_paths(shared_url)
        if not shared_paths_list:
            self.logger.info("共享链接中没有文件或访问失败后未能正确设置会话。")
            return

        shared_paths_deque = deque(shared_paths_list)
        _remote_dirs: Dict[PcsSharedPath, str] = dict(
            [(sp, remote_dir) for sp in shared_paths_deque]
        )
        _dir_exists: Set[str] = set()

        while shared_paths_deque:
            shared_path = shared_paths_deque.popleft()
            rd = _remote_dirs[shared_path]

            if rd not in _dir_exists:
                if not await self.exists(rd):
                    await self.mkdir(rd)
                _dir_exists.add(rd)

            if shared_path.is_file and await self.remote_path_exists(
                PurePosixPath(shared_path.path).name, rd
            ):
                self.logger.warning(f"{shared_path.path} has be in {rd}")
                continue

            uk, share_id_val, bdstoken_val = (
                shared_path.uk,
                shared_path.share_id,
                shared_path.bdstoken,
            )

            try:
                await self.transfer_shared_paths(
                    rd, [shared_path.fs_id], uk, share_id_val, bdstoken_val, shared_url
                )
                self.logger.info(f"save: {shared_path.path} to {rd}")
                continue
            except BaiduApiError as err:
                if err.error_code == 12:
                    self.logger.warning(
                        f"error_code: {err.error_code}, 文件已经存在, {shared_path.path} has be in {rd}"
                    )
                elif err.error_code == -32:
                    self.logger.error(f"error_code:{err.error_code} 剩余空间不足，无法转存")
                elif err.error_code == -33:
                    self.logger.error(
                        f"error_code:{err.error_code} 一次支持操作999个，减点试试吧"
                    )
                elif err.error_code == 4:
                    self.logger.error(
                        f"error_code:{err.error_code} share transfer pcs error"
                    )
                elif err.error_code == 130:
                    self.logger.error(f"error_code:{err.error_code} 转存文件数超限")
                elif err.error_code == 120:
                    self.logger.error(f"error_code:{err.error_code} 转存文件数超限")
                else:
                    self.logger.error(f"转存 {shared_path.path} 失败: error_code:{err.error_code}:{err}")
                    continue

            if shared_path.is_dir:
                sub_paths = await self.list_all_sub_paths(
                    shared_path.path, uk, share_id_val, bdstoken_val
                )
                current_dir_name = PurePosixPath(shared_path.path).name
                sub_remote_dir = (Path(rd) / current_dir_name).as_posix()
                
                for sp in sub_paths:
                    _remote_dirs[sp] = sub_remote_dir
                shared_paths_deque.extendleft(sub_paths[::-1])

    async def remote_path_exists(
        self, name: str, rd: str, _cache: Dict[str, Set[str]] = {}
    ) -> bool:
        """检查远程路径是否存在"""
        
        names = _cache.get(rd)
        if not names:
            listed_items = self.list(rd)
            names = set([PurePosixPath(item.get('path', '')).name for item in listed_items if item.get('path')])
            _cache[rd] = names
        return name in names

    async def list_all_sub_paths(
        self, shared_path: str, uk: int, share_id: int, bdstoken: str, size=100
    ) -> List[PcsSharedPath]:
        """列出所有子路径"""
        
        sub_paths = []
        for page in range(1, 1000):
            sps = await self.list_shared_paths(
                shared_path, uk, share_id, bdstoken, page=page, size=size
            )
            sub_paths.extend(sps)
            if len(sps) < size:
                break
        return sub_paths
        
    async def get_relationship_list(self, params: RelationshipParam, **kwargs: Any) -> Union[List[GetUserFriendDetail], List[GetUserGroupDetail], List[Any]]:
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
        limit = 20 # 百度API通常限制为20
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
                self.logger.error(f"获取 {relationship_type} 列表时API出错: {e}")
                break
            except Exception as e:
                self.logger.error(f"获取 {relationship_type} 列表时发生未知错误: {e}")
                break
            
            if response is None:
                self.logger.error(f"获取 {relationship_type} 列表后响应为空，可能在API调用后出现意外情况。")
                break
            
            if response.get("errno") != 0:
                self.logger.error(f"获取 {relationship_type} 列表失败: {response}")
                break
            
            records = response.get("records", [])
            if not records:
                self.logger.debug(f"第 {iteration_count} 次迭代未获取到记录，结束循环")
                break
            
            # 记录本次获取的数量
            records_count = len(records)
            self.logger.debug(f"第 {iteration_count} 次迭代获取到 {records_count} 条记录")
            
            for record in records:
                if relationship_type == RelationshipType.FRIEND:
                    try:
                        # 映射API返回的好友数据到GetUserFriendDetail模型
                        friend_data = {
                            "uk": int(record.get("uk", 0)),
                            "uname": record.get("uname", ""),
                            "nick_name": record.get("nick_name", ""),
                            "avatar_url": record.get("avatar_url", ""),
                            "is_friend": record.get("is_friend", 2)
                        }
                        item = GetUserFriendDetail(**friend_data)
                    except Exception as e:
                        self.logger.error(f"解析好友数据失败: {record}, 错误: {e}")
                        continue
                elif relationship_type == RelationshipType.GROUP:
                    try:
                        # 映射API返回的群组数据到GetUserGroupDetail模型
                        group_data = {
                            "gid": str(record.get("gid", "")),
                            "gnum": str(record.get("gnum", "")),
                            "name": record.get("name", ""),
                            "type": str(record.get("type", "0")),
                            "status": str(record.get("status", "1"))
                        }
                        item = GetUserGroupDetail(**group_data)
                    except Exception as e:
                        self.logger.error(f"解析群组数据失败: {record}, 错误: {e}")
                        continue
                else:
                    self.logger.warning(f"未知的关系类型: {relationship_type}")
                    return []
                all_items.append(item)
            
            # 检查是否还有更多数据
            has_more = False
            if relationship_type == RelationshipType.FRIEND:
                has_more = response.get("has_more", False)
            elif relationship_type == RelationshipType.GROUP:
                total_count = response.get("count", 0)
                current_fetched = start + records_count
                has_more = current_fetched < total_count and response.get("has_more", True)
            
            # 如果没有更多数据或者本次获取的记录数少于限制数，则结束循环
            if not has_more or records_count < limit:
                self.logger.debug(f"结束循环: has_more={has_more}, records_count={records_count}, limit={limit}")
                break
            
            start += limit
        
        if iteration_count >= max_iterations:
            self.logger.warning(f"达到最大迭代次数 {max_iterations}，强制结束循环")
        
        self.logger.info(f"获取 {relationship_type} 列表完成，共 {len(all_items)} 项，迭代 {iteration_count} 次")
        return all_items

    async def get_relationship_share_list(self,relationship_type: str,identifier: str,type: int = 2,**kwargs) -> Dict:
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
        if relationship_type == "friend":
            # 对于好友分享，limit 和 desc 不是 get_friend_share_list 的直接参数
            # 如果它们在 kwargs 中，会传递给底层 API，但可能被忽略
            return await self._baidupcs.get_friend_share_list(to_uk=identifier, type=type, **kwargs)
        elif relationship_type == "group":
            # 从 kwargs 中提取群组特定的参数，如果未提供则使用默认值
            group_limit = kwargs.pop('limit', 50)
            group_desc = kwargs.pop('desc', 1)
            return await self._baidupcs.get_group_share_list(
                gid=identifier, type=type, limit=group_limit, desc=group_desc, **kwargs
            )
        else:
            self.logger.error(f"无效的 relationship_type: {relationship_type}. 必须是 'friend' 或 'group'.")
            return {"errno": -1, "error_msg": f"无效的 relationship_type: {relationship_type}", "records": []} 
        
    async def get_relationship_share_detail(self,relationship_type: str,identifier: str,from_uk: str,msg_id: str,fs_id: str,page: int = 1,num: int = 50,**kwargs) -> Dict:
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
        if relationship_type == "friend":
            # 如果 'type' 在 kwargs 中，则使用它，否则默认为 1
            final_type = kwargs.pop('type', 1)
            
            # 确保有有效的用户ID
            current_user_id = self.user_id
            if current_user_id is None:
                # 如果没有用户ID，尝试获取
                user_info_response = await self._baidupcs.get_user_info()
                if isinstance(user_info_response, dict):
                    user_info = user_info_response.get("user_info", {})
                    if isinstance(user_info, dict):
                        current_user_id = int(user_info.get("uk")) if user_info.get("uk") is not None else None
                        if current_user_id:
                            self._baidupcs._user_id = current_user_id
                            
            if current_user_id is None:
                self.logger.error("获取好友分享详情失败: 无法获取当前用户ID，请检查登录状态")
                return {"errno": -1, "error_msg": "无法获取当前用户ID，请检查登录状态"}
            
            return await self._baidupcs.get_friend_share_detail(
                from_uk=from_uk,
                msg_id=msg_id,
                to_uk=str(current_user_id),  # 使用获取到的用户ID作为接收者
                fs_id=fs_id,
                type=final_type,
                page=page,
                num=num,
                **kwargs  # 传递剩余的 kwargs
            )
        elif relationship_type == "group":
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
                **kwargs  # 传递剩余的 kwargs
            )
        else:
            self.logger.error(f"无效的 relationship_type: {relationship_type}. 必须是 'friend' 或 'group'.")
            return {"errno": -1, "error_msg": f"无效的 relationship_type: {relationship_type}"}

    async def get_share_list(self, params: ListShareFilesParam, **kwargs: Any) -> List[BaseFileInfo]:  
        """
        获取分享文件列表
        
        :param params: 分享文件列表参数
        :param kwargs: 其他参数，包括 item_filter
        :return: 文件信息列表
        """
        source_type = params.source_type
        source_id = params.source_id
        file_path = params.file_path
        recursive = params.recursive
        recursion_speed = params.recursion_speed
        
        # 获取过滤器参数
        item_filter = kwargs.get('item_filter', None)
        
        drive_files_list: List[BaseFileInfo] = []

        normalized_file_path = file_path.strip('/')
        if not normalized_file_path:
            # 当 file_path 为根路径 "/" 时，返回所有分享的根项目
            self.logger.info(f"Requesting root share items list for {source_type} {source_id}")
            
            # 1. Get all share events/messages
            share_events_response = await self.get_relationship_share_list(
                relationship_type=source_type,
                identifier=source_id
            )

            if share_events_response.get("errno", 0) != 0:
                self.logger.error(f"Failed to get share events for {source_type} {source_id}: {share_events_response}")
                return []

            share_messages = []
            records_obj = share_events_response.get("records", {})
            if source_type == "friend":
                share_messages = records_obj.get("list", [])
            elif source_type == "group":
                share_messages = records_obj.get("msg_list", [])
            
            if not share_messages:
                self.logger.info(f"No share messages found for {source_type} {source_id}.")
                return []

            # 2. 为每个分享事件创建根项目 BaseFileInfo
            for share_event in share_messages:
                msg_id = share_event.get("msg_id")
                sharer_uk = None
                share_root_items_list = [] 

                if source_type == "friend":
                    sharer_uk = share_event.get("from_uk")
                    share_root_items_list = share_event.get("filelist", {}).get("list", [])
                elif source_type == "group":
                    sharer_uk = share_event.get("uk") 
                    share_root_items_list = share_event.get("file_list", [])  # 对于群组是直接的列表
                
                if not msg_id or sharer_uk is None or not share_root_items_list:
                    self.logger.debug(f"跳过分享事件，缺少必要信息 (msg_id, sharer_uk, 或根项目): {share_event}")
                    continue

                share_event_root_item = share_root_items_list[0]  # 假设第一个项目是主要的分享根
                root_item_name = share_event_root_item.get("server_filename")
                root_item_fs_id = share_event_root_item.get("fs_id")

                if not root_item_name or root_item_fs_id is None:
                    self.logger.debug(f"跳过分享事件的根项目，缺少名称/fs_id: {share_event_root_item}")
                    continue
                
                # 为根路径创建 BaseFileInfo
                root_drive_file = BaseFileInfo(
                    file_id=str(root_item_fs_id),
                    file_name=root_item_name,
                    file_path=f"/{root_item_name}",
                    file_size=share_event_root_item.get("size", 0),
                    is_folder=bool(share_event_root_item.get("isdir", 0)),
                    created_at=str(share_event_root_item.get("server_ctime", "")),
                    updated_at=str(share_event_root_item.get("server_mtime", "")),
                    parent_id="",  # 根项目没有父ID
                    file_ext={
                        "from_uk": str(sharer_uk),
                        "msg_id": str(msg_id),
                    }
                )
                
                if item_filter and item_filter.should_exclude(root_drive_file):
                    continue
                
                drive_files_list.append(root_drive_file)
            
            return drive_files_list
        
        # 对于非根路径，解析路径组件
        path_components = normalized_file_path.split('/')

        # 1. Get all share events/messages
        share_events_response = await self.get_relationship_share_list(
            relationship_type=source_type,
            identifier=source_id
        )

        if share_events_response.get("errno", 0) != 0:
            self.logger.error(f"Failed to get share events for {source_type} {source_id}: {share_events_response}")
            return []

        share_messages = []
        records_obj = share_events_response.get("records", {})
        if source_type == "friend":
            share_messages = records_obj.get("list", [])
        elif source_type == "group":
            share_messages = records_obj.get("msg_list", [])
        
        if not share_messages:
            self.logger.info(f"No share messages found for {source_type} {source_id}.")
            return []

        target_share_info = None

        for share_event in share_messages:
            msg_id = share_event.get("msg_id")
            sharer_uk = None
            share_root_items_list = [] 

            if source_type == "friend":
                sharer_uk = share_event.get("from_uk")
                share_root_items_list = share_event.get("filelist", {}).get("list", [])
            elif source_type == "group":
                sharer_uk = share_event.get("uk") 
                share_root_items_list = share_event.get("file_list", [])  # 对于群组是直接的列表
            
            if not msg_id or sharer_uk is None or not share_root_items_list:
                self.logger.debug(f"跳过分享事件，缺少必要信息 (msg_id, sharer_uk, 或根项目): {share_event}")
                continue

            share_event_root_item = share_root_items_list[0]  # 假设第一个项目是主要的分享根
            root_item_name = share_event_root_item.get("server_filename")
            
            root_item_fs_id = share_event_root_item.get("fs_id")

            if not root_item_name or root_item_fs_id is None:
                self.logger.debug(f"跳过分享事件的根项目，缺少名称/fs_id: {share_event_root_item}")
                continue
            
            if path_components[0] == root_item_name:
                target_share_info = {
                    "msg_id": str(msg_id),
                    "sharer_uk": str(sharer_uk),
                    "root_fs_id": str(root_item_fs_id),
                    "root_name": str(root_item_name) 
                }
                # self.logger.info(f"通过根名称 '{root_item_name}' 匹配到分享事件: {target_share_info}")
                break  # 找到目标分享事件
        
        if not target_share_info:
            self.logger.warning(f"No share event found with root item named '{path_components[0]}' for {source_type} {source_id}.")
            return []

        # 3. Navigate the path within the selected share
        current_nav_fs_id = target_share_info["root_fs_id"]
        current_constructed_drive_path = PurePosixPath("/") / target_share_info["root_name"]

        for component_idx in range(1, len(path_components)):
            component_name = path_components[component_idx]
            self.logger.debug(f"Navigating: current_fs_id={current_nav_fs_id}, seeking component='{component_name}'")

            detail_response = await self.get_relationship_share_detail(
                relationship_type=source_type,
                identifier=source_id, 
                from_uk=target_share_info["sharer_uk"],
                msg_id=target_share_info["msg_id"],
                fs_id=current_nav_fs_id
            )

            if detail_response.get("errno") != 0:
                self.logger.error(f"Navigation failed at component '{component_name}' (under fs_id: {current_nav_fs_id}). Response: {detail_response}")
                return []

            items_in_current_dir = detail_response.get("records", [])
            found_next_component = False
            for item_dict in items_in_current_dir:
                item_name_api = item_dict.get("server_filename")
                if item_name_api == component_name:
                    if not item_dict.get("isdir") and component_idx < len(path_components) - 1:
                        self.logger.error(f"Path component '{component_name}' is a file, but further path components exist in query.")
                        return []
                    current_nav_fs_id = str(item_dict.get("fs_id"))
                    current_constructed_drive_path = current_constructed_drive_path / component_name
                    found_next_component = True
                    self.logger.debug(f"Found path component '{component_name}', new current_nav_fs_id={current_nav_fs_id}, new_path_base={current_constructed_drive_path}")
                    break
            
            if not found_next_component:
                self.logger.error(f"Path component '{component_name}' not found in directory (fs_id of parent: { (path_components[component_idx-1] if component_idx > 0 else target_share_info['root_name']) }).")
                return []
        
        # 4. 列出目标内容 (current_nav_fs_id 是要列出的目标 fs_id)
        queue = deque([(str(current_nav_fs_id), current_constructed_drive_path, str(current_nav_fs_id))])
        # 队列存储: (要列出其内容的fs_id, 其内容的路径基础, 从中列出项目的父ID)
        
        processed_fs_ids_for_recursion = set()
        is_first_pass_in_queue = True  # 用于识别目标路径的初始列表

        while queue:
            fs_id_to_process, path_base_for_items, parent_id_for_items = queue.popleft()

            if fs_id_to_process in processed_fs_ids_for_recursion and recursive:
                 continue
            if recursive:  # 仅在递归模式下添加到已处理列表
                processed_fs_ids_for_recursion.add(fs_id_to_process)

            # 仅在启用递归时应用递归速度逻辑
            if recursive and not is_first_pass_in_queue:  # 速度逻辑适用于子目录处理，而不是初始目标路径
                if recursion_speed == RecursionSpeed.SLOW:
                    self.logger.debug(f"慢速模式 (分享): 在列出 fs_id: {fs_id_to_process} 之前暂停 3 秒")
                    time.sleep(3)
                elif recursion_speed == RecursionSpeed.FAST:
                    # 快速模式：尝试从缓存获取子目录内容
                    if kwargs.get('drive_account_id') and kwargs.get('db'):
                        try:
                            from backend.app.coulddrive.service.file_cache_service import file_cache_service
                            
                            # 为分享文件构建特殊的缓存键，包含分享信息
                            share_cache_key = f"share_{source_type}_{source_id}_{fs_id_to_process}"
                            
                            cached_children = await file_cache_service.get_cached_children_as_file_info(
                                kwargs['db'], 
                                parent_id=share_cache_key, 
                                drive_account_id=kwargs['drive_account_id']
                            )
                            
                            if cached_children:
                                self.logger.debug(f"快速模式：从缓存获取分享子目录 fs_id: {fs_id_to_process}")
                                # 将缓存的子项添加到结果列表
                                for cached_child in cached_children:
                                    # 应用过滤器
                                    if not (item_filter and item_filter.should_exclude(cached_child)):
                                        drive_files_list.append(cached_child)
                                        
                                        # 如果是文件夹且启用递归，添加到队列
                                        if cached_child.is_folder and recursive:
                                            child_cache_key = f"share_{source_type}_{source_id}_{cached_child.file_id}"
                                            queue.append((cached_child.file_id, PurePosixPath(cached_child.file_path), cached_child.file_id))
                                continue
                            else:
                                self.logger.debug(f"快速模式：缓存中无分享子目录数据，回退到API获取 fs_id: {fs_id_to_process}")
                        except Exception as e:
                            self.logger.warning(f"快速模式缓存获取失败，回退到API: {e}")
                    else:
                        self.logger.debug(f"快速模式：缺少必要参数，跳过分享子目录递归 fs_id: {fs_id_to_process}")
                        continue
            
            if is_first_pass_in_queue:
                is_first_pass_in_queue = False  # 标记队列中的第一个项目已被处理

            self.logger.debug(f"Listing content for fs_id: {fs_id_to_process}, path_base: {path_base_for_items}, items_parent_id: {parent_id_for_items}")
            detail_response = await self.get_relationship_share_detail(
                relationship_type=source_type,
                identifier=source_id, 
                from_uk=target_share_info["sharer_uk"],
                msg_id=target_share_info["msg_id"],
                fs_id=fs_id_to_process
            )

            if detail_response.get("errno") != 0:
                self.logger.warning(f"Failed to get details for fs_id {fs_id_to_process} during final listing: {detail_response}")
                continue
            
            items_from_api = detail_response.get("records", [])
            
            # 检查 fs_id_to_process 本身是否是文件
            # 如果 fs_id_to_process 是文件，items_from_api 将只包含该文件
            is_listing_a_single_target_file = False
            if len(items_from_api) == 1 and str(items_from_api[0].get("fs_id")) == fs_id_to_process and not items_from_api[0].get("isdir"):
                is_listing_a_single_target_file = True
                self.logger.debug(f"列出的目标 fs_id {fs_id_to_process} 是单个文件。")

            for item_dict in items_from_api:
                item_fs_id_str = str(item_dict.get("fs_id"))
                item_name = item_dict.get("server_filename", "Unknown")
                is_folder_item = bool(item_dict.get("isdir"))
                
                # 构建 BaseFileInfo 路径:
                # 如果列出单个目标文件，其路径是 path_base_for_items。
                # 如果列出目录的内容，项目的路径是 path_base_for_items / item_name。
                drive_file_item_path_str = str(path_base_for_items if is_listing_a_single_target_file else path_base_for_items / item_name)

                df = BaseFileInfo(
                    file_id=item_fs_id_str,
                    file_name=item_name,
                    file_path=drive_file_item_path_str,
                    file_size=item_dict.get("size", 0),
                    is_folder=is_folder_item,
                    created_at=str(item_dict.get("server_ctime")),  # API 使用 server_ctime
                    updated_at=str(item_dict.get("server_mtime")),  # API 使用 server_mtime
                    parent_id=str(parent_id_for_items),
                    file_ext={
                        "from_uk": target_share_info["sharer_uk"],
                        "msg_id": target_share_info["msg_id"],
                        # 如果需要，也可以保留原始API项目的部分或全部信息
                        # "baidu_api_item": dict(item_dict),
                        #"sharer_original_path": item_dict.get("path")
                    }
                )

                if item_filter and item_filter.should_exclude(df):
                    if df.is_folder and recursive:  # 如果文件夹被排除，不要将其子项添加到队列
                        # 我们需要确保此 df.file_id 以后不会添加到队列
                        # 当前逻辑在此检查*之后*基于 df.is_folder 添加到队列
                        # 所以，如果被排除，它不会在下面添加到队列。这很好。
                        pass 
                    continue  # 跳过添加到 drive_files_list 和队列的进一步处理
                
                drive_files_list.append(df)

                if recursive and is_folder_item and not is_listing_a_single_target_file:
                    # 过滤器已应用于 df。如果没有被排除，可以添加到队列。
                    queue.append((df.file_id, PurePosixPath(drive_file_item_path_str), df.file_id))
            
            if is_listing_a_single_target_file:  # 如果初始目标是文件，我们已经列出了它，所以停止。
                break
        
        # 自动写入缓存（分享文件）
        if drive_files_list and kwargs.get('drive_account_id') and kwargs.get('db'):
            try:
                from backend.app.coulddrive.service.file_cache_service import file_cache_service
                
                # 为分享文件构建特殊的缓存键
                share_cache_key = f"share_{source_type}_{source_id}"
                
                await file_cache_service.smart_cache_write(
                    kwargs['db'],
                    drive_account_id=kwargs['drive_account_id'],
                    files=drive_files_list
                )
                self.logger.debug(f"分享文件列表缓存写入成功，共 {len(drive_files_list)} 个文件")
            except Exception as e:
                self.logger.warning(f"分享文件列表缓存写入失败: {e}")
        
        return drive_files_list
        
    async def transfer(self,params: TransferParam, **kwargs: Any) -> bool:
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
        source_path = params.source_path
        target_path = params.target_path
        file_ids = params.file_ids

        # 合并 params.ext 和 kwargs，params.ext 中的参数优先级更高
        combined_kwargs = {}
        combined_kwargs.update(kwargs)
        if params.ext:
            combined_kwargs.update(params.ext)

        # 确保target_path使用正斜杠
        target_path = target_path.replace("\\", "/")
        
        self.logger.info(
            f"转存请求: source_type='{source_type}', source_id='{source_id}', "
            f"source_path='{source_path}', target_path='{target_path}', file_ids='{file_ids}'"
        )

        # 确保用户ID可用
        current_user_id = self.user_id
        if current_user_id is None:
            # 如果没有用户ID，尝试获取
            user_info_response = await self._baidupcs.get_user_info()
            if isinstance(user_info_response, dict):
                user_info = user_info_response.get("user_info", {})
                if isinstance(user_info, dict):
                    current_user_id = int(user_info.get("uk")) if user_info.get("uk") is not None else None
                    if current_user_id:
                        self._baidupcs._user_id = current_user_id
                        
        if not current_user_id:
            self.logger.error("转存失败: 无法获取用户ID，请检查登录状态")
            return False

        if source_type == "link":
            self.logger.warning("来自 'link' 类型的转存尚未为百度网盘实现.")
            # TODO: 如果接口适用，在此处实现 save_shared 或类似逻辑
            # 目前根据用户请求，这是一个占位符。
            # self.save_shared(shared_url=source_id, remote_dir=target_path, password=kwargs.get("password"))
            # save_shared 方法本身需要调整以返回简单的布尔值。
            raise NotImplementedError("百度客户端尚不支持从 'link' 类型转存.")

        elif source_type in ["friend", "group"]:
            if not file_ids:
                self.logger.error(f"转存失败: source_type '{source_type}' 需要 'file_ids'.")
                return False
            
            msg_id = combined_kwargs.get("msg_id")
            if not msg_id:
                self.logger.error(f"转存失败: source_type '{source_type}' 的参数中需要 'msg_id'.")
                return False

            transfer_type = 1 if source_type == "friend" else 2
            
            # 构建API参数
            api_kwargs = {
                "path": target_path,
                "ondup": combined_kwargs.get("ondup", "newcopy"),
            }
            
            # 处理异步参数 - 简化逻辑
            async_value = combined_kwargs.get("async_", combined_kwargs.get("async", 1))
            api_kwargs["async_"] = int(async_value) if async_value is not None else 1


            from_uk_param = None

            if source_type == "friend":
                from_uk_param = source_id  # source_id 是好友的 UK (分享者 UK)
            elif source_type == "group":
                # source_id 是群组的 ID (gid)
                # api.py 中的 `transfer_files` 方法需要 `from_uk` (分享者) 和 `gid` (群组)
                from_uk_param = combined_kwargs.get("from_uk")  # 参数中必须提供分享者的 UK
                if not from_uk_param:
                    self.logger.error("群组分享转存失败: 参数中需要 'from_uk' (分享者 UK).")
                    return False
                api_kwargs["gid"] = source_id  # 将 gid 传递给 transfer_files 的 api_kwargs


            try:
                result = await self._baidupcs.transfer_files(
                    from_uk=str(from_uk_param) if from_uk_param else "",
                    to_uk=str(current_user_id),
                    msg_id=str(msg_id),
                    fs_ids=file_ids,
                    type=transfer_type,
                    **api_kwargs
                )
                if result.get("errno") == 0:
                    self.logger.info(f"source_type '{source_type}' 转存成功. API 响应: {result}")
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
            self.logger.error(f"不支持的转存 source_type: {source_type}")
            return False