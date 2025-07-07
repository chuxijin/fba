#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created On: 2024-01-01
@Author: PanMaster团队
夸克网盘客户端实现
"""

from __future__ import annotations
import asyncio
from collections import deque
from datetime import datetime
from io import BytesIO
import logging
import os
from pathlib import Path, PurePosixPath
import re
import time
from typing import Any, Callable, Dict, IO, List, Optional, Set, Tuple, Union

from backend.app.coulddrive.schema.enum import RecursionSpeed
from backend.app.coulddrive.schema.file import (
    BaseFileInfo,
    BaseShareInfo,
    ListFilesParam,
    ListShareFilesParam,
    ListShareInfoParam,
    MkdirParam,
    ShareParam,
    RelationshipParam,
    RelationshipType,
    RemoveParam,
    TransferParam,
    UserInfoParam,
)
from backend.app.coulddrive.schema.user import (
    BaseUserInfo,
    GetUserFriendDetail,
    GetUserGroupDetail,
)
from backend.app.coulddrive.service.filesync_service import ItemFilter
from backend.app.coulddrive.service.quark.api import QuarkApi
from backend.app.coulddrive.service.quark.errors import QuarkApiError
from backend.app.coulddrive.service.yp_service import BaseDriveClient
from backend.common.log import log

from .schemas import (
    FromTo,
    QuarkAccount,
    QuarkAuthor,
    QuarkFile,
    QuarkMember,
    QuarkSaveTask,
    QuarkShare,
    QuarkShareDetail,
    QuarkTask,
)

SHARED_URL_PREFIX = "https://pan.quark.cn/s/"


def _unify_shared_url(url: str) -> str:
    """统一输入的分享链接格式"""
    
    # 标准链接格式
    temp = r"pan\.quark\.cn/s/(.+?)(\?|$)"
    m = re.search(temp, url)
    if m:
        return SHARED_URL_PREFIX + m.group(1)
    
    raise ValueError(f"The shared url is not a valid url. {url}")


def _extract_pwd_id_from_url(url: str) -> str:
    """从分享链接中提取pwd_id，或者直接返回pwd_id"""
    
    # 如果输入看起来已经是pwd_id（不包含域名），直接返回
    if not ("pan.quark.cn" in url or "http" in url):
        return url.strip()
    
    # 标准链接格式: https://pan.quark.cn/s/xxxxx 或 https://pan.quark.cn/s/xxxxx#/list/share
    temp = r"pan\.quark\.cn/s/(.+?)(\?|#|$)"
    m = re.search(temp, url)
    if m:
        return m.group(1)
    
    raise ValueError(f"无法从分享链接中提取pwd_id: {url}")


def _parse_share_url_and_password(source_id: str) -> Tuple[str, str]:
    """
    解析分享链接和密码
    
    :param source_id: 分享链接，可能包含密码，格式如 "https://pan.quark.cn/s/xxxxx" 或 "https://pan.quark.cn/s/xxxxx|password"
    :return: (pwd_id, password) 元组
    """
    if "|" in source_id:
        url, password = source_id.split("|", 1)
        pwd_id = _extract_pwd_id_from_url(url.strip())
        return pwd_id, password.strip()
    else:
        pwd_id = _extract_pwd_id_from_url(source_id.strip())
        return pwd_id, ""


class QuarkClient(BaseDriveClient):
    """夸克网盘客户端
    
    这是对`QuarkApi`的封装。它将原始QuarkApi请求的响应内容解析为一些内部数据结构。
    """

    def __init__(
        self,
        cookies: str,
        user_id: Optional[str] = None,
    ):
        """
        
        :param cookies: cookies 字符串，格式如 "key1=value1; key2=value2"
        :param user_id: 用户ID
        """
        super().__init__()
        # 初始化日志记录器
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 不要先创建空的 QuarkApi 实例，直接在 login 中创建
        self._quarkapi: QuarkApi = None
        self._is_authorized = False

        # 自动登录
        if self.login(cookies, user_id):
            pass
        else:
            raise ValueError("QuarkClient 初始化失败：登录失败")

    @property
    def drive_type(self) -> str:
        return "QuarkDrive"
    


    def login(self, cookies: str, user_id: Optional[str] = None) -> bool:
        """
        登录夸克网盘
        
        :param cookies: cookies 字符串，格式如 "key1=value1; key2=value2"
        :param user_id: 用户ID
        :return: 是否登录成功
        """
        # 检查是否有有效的认证信息
        has_cookies = cookies and cookies.strip()
        
        if has_cookies:
            try:
                self._quarkapi = QuarkApi(cookies=cookies)
                
                if self._quarkapi._cookies:
                    # 通过获取用户信息来验证登录
                    try:
                        async def verify_login():
                            try:
                                account_info = await self._quarkapi.get_account_info()
                                if isinstance(account_info, dict) and account_info.get("code") == 0:
                                    return True
                            except Exception:
                                pass
                            return False
                        
                        # 尝试在当前上下文中运行验证
                        try:
                            loop = asyncio.get_running_loop()
                            # 在异步上下文中，暂时标记为已授权
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
                self.logger.error(f"QuarkApi 初始化失败: {e}")
                self._is_authorized = False
                return False
        
        # 如果没有认证信息且_quarkapi为None，返回False
        if self._quarkapi is None:
            self._is_authorized = False
            return False
            
        return self._is_authorized

    @property
    def user_id(self) -> Optional[str]:
        """获取用户ID，如果没有则返回None"""
        if self._quarkapi and self._quarkapi._user_id:
            return self._quarkapi._user_id
        return None

    @property
    def cookies(self) -> Dict[str, str]:
        return self._quarkapi.cookies if self._quarkapi else {}

    async def quota(self) -> Dict[str, Any]:
        """获取配额信息"""
        info = await self._quarkapi.get_member_info()
        return {
            "quota": info.get("data", {}).get("total_capacity", 0),
            "used": info.get("data", {}).get("use_capacity", 0)
        }

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
            # 获取账户信息
            account_info = await self._quarkapi.get_account_info()
            # 获取会员信息
            member_info = await self._quarkapi.get_member_info()
            
            if (isinstance(account_info, dict) and account_info.get('code') == 'OK' and
                isinstance(member_info, dict) and member_info.get('code') == 0):
                
                account_data = account_info.get('data', {})
                member_data = member_info.get('data', {})
                
                return BaseUserInfo(
                    user_id=str(account_data.get('mobilekps', '')),
                    username=account_data.get('nickname', ''),
                    avatar_url=account_data.get('avatarUri', ''),
                    quota=member_data.get('total_capacity', 0),
                    used=member_data.get('use_capacity', 0),
                    is_vip=member_data.get('is_vip', False),
                    is_supervip=member_data.get('member_type') == 'SUPER_VIP'
                )
            else:
                error_msg = account_info.get('message', '未知错误') if isinstance(account_info, dict) else str(account_info)
                self.logger.error(f"获取用户信息失败: {error_msg}")
                return BaseUserInfo(user_id='0', username='未知用户', avatar_url='', is_vip=False, is_supervip=False)
        except Exception as e:
            self.logger.error(f"获取用户信息时发生错误: {e}")
            return BaseUserInfo(user_id='0', username='未知用户', avatar_url='', is_vip=False, is_supervip=False)

    async def meta(self, *file_paths: str) -> List[QuarkFile]:
        """获取`file_paths`的元数据"""
        # 夸克网盘通过路径获取文件信息
        info = await self._quarkapi.get_file_info_by_path(list(file_paths))
        return [QuarkFile.from_(v) for v in info.get("data", [])]

    async def exists(self, file_path: str) -> bool:
        """检查`file_path`是否存在"""
        try:
            info = await self._quarkapi.get_file_info_by_path([file_path])
            return len(info.get("data", [])) > 0
        except Exception:
            return False

    async def is_file(self, file_path: str) -> bool:
        """检查`file_path`是否是文件"""
        try:
            info = await self._quarkapi.get_file_info_by_path([file_path])
            data = info.get("data", [])
            if data:
                return not data[0].get("dir", False)
        except Exception:
            pass
        return False

    async def is_dir(self, file_path: str) -> bool:
        """检查`file_path`是否是目录"""
        try:
            info = await self._quarkapi.get_file_info_by_path([file_path])
            data = info.get("data", [])
            if data:
                return data[0].get("dir", False)
        except Exception:
            pass
        return False

    async def get_disk_list(self, params: ListFilesParam, **kwargs: Any) -> List[BaseFileInfo]:
        """
        获取目录下的文件和目录列表（单层，不递归）
        
        :param params: 文件列表查询参数
        :param kwargs: 其他关键字参数
        """
        # 从 params 中提取参数
        file_path = params.file_path or "/"
        file_id = params.file_id or ""
        
        # 从 kwargs 中获取可选参数
        drive_account_id = kwargs.get('drive_account_id', None)
        db = kwargs.get('db', None)

        # 构建排序参数
        sort_str = "file_type:asc,updated_at:desc"  # 默认排序

        drive_files_list: List[BaseFileInfo] = []
        
        # 确定初始的 pdir_fid
        initial_pdir_fid = file_id if file_id else "0"  # 根目录使用 "0"
        
        async def fetch_all_quark_pages_from_api(pdir_fid: str, sort_str: str) -> List[Dict]:
            """
            自动翻页获取夸克网盘指定目录下的所有文件/目录（单层）
            
            :param pdir_fid: 父目录ID
            :param sort_str: 排序字符串
            :return: 所有页面的文件列表
            """
            page = 1
            page_size = 50
            all_items = []
            
            while True:
                try:
                    info = await self._quarkapi.list_files(
                        pdir_fid=pdir_fid,
                        page=page,
                        size=page_size,
                        sort=sort_str
                    )
                    
                    current_items = info.get("data", {}).get("list", [])
                    all_items.extend(current_items)
                    
                    # 检查是否还有更多数据
                    metadata = info.get("metadata", {})
                    current_count = metadata.get("_count", 0)
                    
                    # 如果本页返回数量小于page_size，说明已经是最后一页
                    if current_count < page_size:
                        break
                    
                    page += 1
                except Exception as e:
                    self.logger.error(f"获取第{page}页数据失败 pdir_fid: {pdir_fid}: {e}")
                    break
            
            return all_items
        
        try:
            # 获取目录内容
            items_raw = await fetch_all_quark_pages_from_api(initial_pdir_fid, sort_str)
        except Exception as e:
            self.logger.error(f"Error listing path '{file_path}' with fid '{initial_pdir_fid}': {e}")
            return []

        # 将API返回的数据转换为BaseFileInfo
        for item_dict in items_raw:
            current_fid = item_dict.get('fid')
            current_item_name = item_dict.get('file_name', '')
            is_folder = bool(item_dict.get('dir', False))
            
            # 构建当前项目的完整路径
            if file_path == "/":
                item_full_path = f"/{current_item_name}"
            else:
                item_full_path = f"{file_path.rstrip('/')}/{current_item_name}"
            
            # 创建 BaseFileInfo 对象
            file_info = BaseFileInfo(
                file_id=current_fid,
                file_name=current_item_name,
                file_path=item_full_path,
                is_folder=is_folder,
                parent_id=initial_pdir_fid,
                file_size=item_dict.get('size', 0),
                created_at=str(item_dict.get('created_at', '')),
                updated_at=str(item_dict.get('updated_at', '')),
                file_ext={}  # 夸克可以根据需要添加扩展信息
            )
            
            drive_files_list.append(file_info)

        return drive_files_list

    async def mkdir(self, params: MkdirParam, **kwargs: Any) -> BaseFileInfo:
        """
        创建目录
        
        :param params: 创建目录参数
        :param kwargs: 其他关键字参数
        """
        try:
            # 从params中提取参数
            parent_id = params.parent_id or "0"
            folder_name = params.file_name
            
            # 调用API创建文件夹
            result = await self._quarkapi.create_folder(
                pdir_fid=parent_id,
                file_name=folder_name
            )
            
            # API 调用成功，直接处理返回数据
            data = result.get("data", {})
            
            # 构建完整路径
            file_path = params.file_path or "/"
            if file_path == '/':
                full_path = f"/{folder_name}"
            else:
                full_path = f"{file_path}/{folder_name}"
            
            # 直接使用原始时间戳
            mkdir_created_at_str = str(data.get('created_at', ''))
            mkdir_updated_at_str = str(data.get('updated_at', ''))
            
            return BaseFileInfo(
                file_id=str(data.get('fid', '')),
                file_path=full_path,
                file_name=folder_name,
                file_size=0,
                is_folder=True,
                created_at=mkdir_created_at_str,
                updated_at=mkdir_updated_at_str,
                parent_id=parent_id,
            )
                
        except Exception as e:
            self.logger.error(f"创建文件夹时发生错误: {e}")
            raise

    async def rename(self, file_id: str, new_name: str) -> bool:
        """重命名文件或文件夹"""
        try:
            await self._quarkapi.rename_file(fid=file_id, file_name=new_name)
            return True
        except Exception as e:
            self.logger.error(f"重命名文件时发生错误: {e}")
            return False

    async def move(self, file_ids: List[str], target_folder_id: str) -> bool:
        """移动文件或文件夹"""
        try:
            await self._quarkapi.move_files(
                file_ids=file_ids,
                to_pdir_fid=target_folder_id
            )
            return True
        except Exception as e:
            self.logger.error(f"移动文件时发生错误: {e}")
            return False

    async def copy(self, file_ids: List[str], target_folder_id: str) -> bool:
        """复制文件或文件夹"""
        try:
            await self._quarkapi.copy_files(
                file_ids=file_ids,
                to_pdir_fid=target_folder_id
            )
            return True
        except Exception as e:
            self.logger.error(f"复制文件时发生错误: {e}")
            return False

    async def remove(self, params: RemoveParam, **kwargs: Any) -> bool:
        """
        删除文件或文件夹
        
        :param params: 删除参数
        :param kwargs: 其他关键字参数
        """
        try:
            # 从params中提取文件ID列表
            file_ids = params.file_ids if hasattr(params, 'file_ids') else []
            if not file_ids and hasattr(params, 'file_id'):
                file_ids = [params.file_id]
            
            if not file_ids:
                return False
                
            await self._quarkapi.delete_files(file_ids=file_ids)
            return True
        except Exception as e:
            self.logger.error(f"删除文件时发生错误: {e}")
            return False

    async def create_share(self, params: ShareParam, **kwargs: Any) -> BaseShareInfo:
        """创建分享链接"""
        file_name = params.file_name
        file_ids = params.file_ids
        expired_type = params.expired_type
        
        # 夸克网盘过期类型转换：统一天数 -> 夸克枚举值
        # 0(永久) -> 1, 1(1天) -> 1, 7(7天) -> 2, 30(30天) -> 3, 365(365天) -> 4
        quark_expired_type_map = {
            0: 1,    # 永久
            1: 2,    # 1天
            7: 3,    # 7天
            30: 4,   # 30天
        }
        
        quark_expired_type = quark_expired_type_map.get(expired_type, 1)  # 默认永久
        
        try:
            # 将字符串ID转换为字符串列表
            fid_list = [str(fid) for fid in file_ids]
            
            # 第1步：创建分享任务
            result = await self._quarkapi.create_share(
                fid_list=fid_list,
                title=file_name,
                expired_type=quark_expired_type,
                url_type=1,  # 添加url_type参数
                **kwargs
            )
            
            data = result.get("data", {})
            task_id = data.get("task_id")
            
            if not task_id:
                raise QuarkApiError("创建分享任务失败：未获取到task_id")
            
            # 第2步：轮询任务状态，等待分享创建完成
            max_retries = 10
            retry_count = 0
            share_id = None
            
            while retry_count < max_retries:
                task_result = await self._quarkapi.query_task(task_id=task_id, retry_index=retry_count)
                task_data = task_result.get("data", {})
                
                if task_data.get("status") == 2:  # 任务完成
                    share_id = task_data.get("share_id")
                    break
                elif task_data.get("status") == 3:  # 任务失败
                    raise QuarkApiError(f"分享任务失败：{task_data}")
                
                # 等待1秒后重试
                await asyncio.sleep(1)
                retry_count += 1
            
            if not share_id:
                raise QuarkApiError("分享任务超时：未能在预期时间内完成")
            
            # 第3步：获取分享详情
            password_result = await self._quarkapi.get_share_password(share_id=share_id)
            share_data = password_result.get("data", {})
            
            # 转换为统一的BaseShareInfo格式
            from datetime import datetime
            
            # 使用API返回的过期时间
            expired_at = None
            if share_data.get("expired_at"):
                expired_at = datetime.fromtimestamp(share_data.get("expired_at") / 1000)  # 毫秒转秒
            
            return BaseShareInfo(
                title=share_data.get("title", file_name),
                share_id=str(share_id),
                pwd_id=str(share_data.get("pwd_id", "")),
                url=share_data.get("share_url", ""),
                password=str(share_data.get("passcode", "")),
                expired_type=expired_type,  # 保持原始的统一天数格式
                view_count=0,
                expired_at=expired_at,
                expired_left=None,
                audit_status=1,  # 假设通过审核
                status=1,
                file_id=str(file_ids[0]) if file_ids else None,
                file_only_num=str(share_data.get("file_num", 0)),  # 转换为字符串
                file_size=share_data.get("size"),
                path_info=str(share_data.get("path_info", "")) if share_data.get("path_info") else None
            )
        except Exception as e:
            self.logger.error(f"创建分享时发生错误: {e}")
            raise

    async def get_share_list(self, params: ListShareFilesParam, **kwargs: Any) -> List[BaseFileInfo]:
        """
        获取指定分享中特定路径下的文件/目录列表（单层，不递归）
        
        :param params: 分享列表参数
        :return: 分享列表
        """
        source_type = params.source_type
        source_id = params.source_id
        file_path = params.file_path
        
        drive_files_list: List[BaseFileInfo] = []

        async def fetch_all_quark_share_pages_from_api(
            pwd_id: str, 
            stoken: str, 
            pdir_fid: str = "0",
            sort: str = "file_type:asc,file_name:asc"
        ) -> List[Dict]:
            """
            自动翻页获取夸克网盘分享文件列表的所有页面数据（单层）
            
            :param pwd_id: 分享密码ID
            :param stoken: 分享token
            :param pdir_fid: 父目录ID
            :param sort: 排序字符串
            :return: 所有页面的文件列表
            """
            page = 1
            page_size = 50
            all_items = []
            
            while True:
                try:
                    detail_response = await self._quarkapi.get_share_detail(
                        pwd_id=pwd_id,
                        stoken=stoken,
                        pdir_fid=pdir_fid,
                        page=page,
                        size=page_size,
                        sort=sort
                    )
                    
                    current_items = detail_response.get("data", {}).get("list", [])
                    all_items.extend(current_items)
                    
                    # 检查是否还有更多数据
                    metadata = detail_response.get("data", {}).get("metadata", {})
                    current_count = metadata.get("_count", 0)
                    
                    # 如果本页返回数量小于page_size，说明已经是最后一页
                    if current_count < page_size:
                        break
                    
                    page += 1
                except Exception as e:
                    self.logger.error(f"获取第{page}页分享数据失败 pdir_fid: {pdir_fid}: {e}")
                    break
            
            return all_items

        # TODO: friend 和 group 类型暂未实现，当前只支持 link 类型
        if source_type in ["friend", "group"]:
            self.logger.warning(f"夸克网盘暂不支持 {source_type} 类型的分享列表获取")
            return []
        
        if source_type != "link":
            self.logger.error(f"不支持的分享类型: {source_type}")
            return []

        # 解析分享链接和密码
        try:
            pwd_id, password = _parse_share_url_and_password(source_id)
            
            # 先获取share_token，直接调用API层
            token_result = await self._quarkapi.get_share_token(pwd_id=pwd_id)
            stoken = token_result.get("data", {}).get("stoken", "")
            
            # 获取文件列表
            file_list = await fetch_all_quark_share_pages_from_api(pwd_id=pwd_id, stoken=stoken)
            if not file_list:
                self.logger.warning(f"分享链接中没有文件: {source_id}")
                return []
            
            # 处理路径导航
            normalized_file_path = file_path.strip('/')
            current_items = file_list
            current_pdir_fid = "0"
            current_path = ""
            
            # 如果不是根路径，需要导航到指定路径
            if normalized_file_path:
                # 解析路径组件进行导航
                path_components = normalized_file_path.split('/')
                
                # 逐级导航到目标路径
                for component in path_components:
                    if not component:
                        continue
                        
                    # 在当前级别查找匹配的项目
                    found_item = None
                    for item in current_items:
                        if item.get("file_name") == component:
                            found_item = item
                            break
                    
                    if not found_item:
                        self.logger.error(f"路径组件 '{component}' 在分享中不存在")
                        return []
                    
                    # 如果不是目录但还有后续路径组件，则路径无效
                    if not found_item.get("dir") and component != path_components[-1]:
                        self.logger.error(f"路径组件 '{component}' 是文件，但后续还有路径组件")
                        return []
                    
                    current_pdir_fid = str(found_item.get("fid", ""))
                    current_path = f"{current_path}/{component}" if current_path else f"/{component}"
                    
                    # 如果是目录且不是最后一个组件，需要获取子目录内容
                    if found_item.get("dir") and component != path_components[-1]:
                        current_items = await fetch_all_quark_share_pages_from_api(
                            pwd_id=pwd_id, 
                            stoken=stoken, 
                            pdir_fid=current_pdir_fid
                        )
                    elif component == path_components[-1]:
                        # 到达目标路径
                        if found_item.get("dir"):
                            # 目标是目录，获取其内容
                            current_items = await fetch_all_quark_share_pages_from_api(
                                pwd_id=pwd_id, 
                                stoken=stoken, 
                                pdir_fid=current_pdir_fid
                            )
                        else:
                            # 目标是文件，返回该文件
                            current_items = [found_item]
            
            # 处理当前目录的项目（单层）
            for item in current_items:
                item_fid = str(item.get("fid", ""))
                item_name = item.get("file_name", "")
                is_dir = bool(item.get("dir", False))
                
                # 构建完整路径
                if current_path == "/":
                    full_path = f"/{item_name}"
                else:
                    full_path = f"{current_path}/{item_name}" if current_path else f"/{item_name}"
                
                # 创建 BaseFileInfo
                drive_file = BaseFileInfo(
                    file_id=item_fid,
                    file_name=item_name,
                    file_path=full_path,
                    file_size=item.get("size", 0),
                    is_folder=is_dir,
                    created_at=str(item.get("created_at", "")),
                    updated_at=str(item.get("updated_at", "")),
                    parent_id=current_pdir_fid,
                    file_ext={
                        "pwd_id": pwd_id,
                        "stoken": stoken,
                        "share_url": source_id,
                        "share_fid_token": item.get("share_fid_token", ""),
                        "pdir_fid": current_pdir_fid,  # 添加父目录ID，供转存时使用
                    }
                )
                
                # self.logger.info(f"获取到分享文件: {item_name}, parent_id: {current_pdir_fid}, file_id: {item_fid}")
                
                drive_files_list.append(drive_file)
            
            return drive_files_list
            
        except Exception as e:
            self.logger.error(f"处理分享链接时发生错误: {e}")
            return []

    async def cancel_share(self, params: 'CancelShareParam', **kwargs: Any) -> bool:
        """
        取消分享链接
        
        :param params: 取消分享参数
        :param kwargs: 其他关键字参数
        :return: 是否成功取消
        """
        from backend.app.coulddrive.schema.file import CancelShareParam
        
        try:
            # 将ID转换为字符串列表
            share_ids = [str(sid) for sid in params.shareid_list]
            await self._quarkapi.cancel_shared(share_ids=share_ids)
            return True
        except Exception as e:
            self.logger.error(f"取消分享时发生错误: {e}")
            return False

    async def get_share_info(self, params: ListShareInfoParam, **kwargs: Any) -> Union[List[BaseShareInfo], Dict[str, Any]]:
        """
        获取分享详情列表
        
        :param params: 分享文件列表查询参数
        :param kwargs: 其他关键字参数，包括分页参数
        :return: 分享详情列表或包含分页信息的字典
        """
        if params.source_type == "link":
            # 外部分享链接信息获取
            pwd_id = _extract_pwd_id_from_url(params.source_id)
            
            # 先获取share_token，@assert_ok装饰器已处理错误检查
            token_result = await self._quarkapi.get_share_token(pwd_id=pwd_id)
            stoken = token_result.get("data", {}).get("stoken", "")
            
            if not stoken:
                self.logger.error(f"获取stoken失败，无法继续")
                return []
            
            # @assert_ok装饰器已处理错误检查，直接处理数据
            result = await self._quarkapi.get_share_detail(pwd_id=pwd_id, stoken=stoken)
            
            # 从API返回的data字段中获取分享信息
            share_data = result.get("data", {})
            share_info_data = share_data.get("share", {})
            
            # 解析为BaseShareInfo对象
            share_info = BaseShareInfo(
                title=share_info_data.get("title", ""),
                share_id=share_info_data.get("share_id", ""),
                pwd_id=share_info_data.get("pwd_id", ""),
                url=share_info_data.get("share_url", ""),
                password=str(share_info_data.get("passcode", "")),
                expired_type=share_info_data.get("expired_type", 0),
                view_count=share_info_data.get("click_pv", 0),
                expired_at=datetime.fromtimestamp(share_info_data.get("expired_at", 0) / 1000) if share_info_data.get("expired_at") else None,
                expired_left=share_info_data.get("expired_left", 0),
                audit_status=share_info_data.get("audit_status", 0),
                status=share_info_data.get("status", 0),
                file_id=share_info_data.get("first_fid", 0),
                file_only_num=str(share_info_data.get("file_num", 0)),
                file_size=share_info_data.get("size", 0),
                path_info=share_info_data.get("path_info", "")
            )
            
            return [share_info]
            
        elif params.source_type == "local":
            # 本地分享列表获取，支持分页
            page = params.page
            size = params.size
            order_field = params.order_field
            order_type = params.order_type
            
            # @assert_ok装饰器已处理错误检查
            result = await self._quarkapi.get_share_page(
                page=page,
                size=size,
                order_field=order_field,
                order_type=order_type
            )
            
            # 解析分享列表（一定会有数据结构）
            share_list = result.get("data", {}).get("list", [])
            metadata = result.get("data", {}).get("metadata", {})
            
            share_info_list = []
            for item in share_list:
                share_info = BaseShareInfo(
                    title=item.get("title", ""),
                    share_id=item.get("share_id", ""),
                    pwd_id=item.get("pwd_id", ""),
                    url=item.get("share_url", ""),
                    password=str(item.get("passcode", "")),
                    expired_type=item.get("expired_type", 0),
                    view_count=item.get("click_pv", 0),
                    expired_at=datetime.fromtimestamp(item.get("expired_at", 0) / 1000) if item.get("expired_at") else None,
                    expired_left=item.get("expired_left", 0),
                    audit_status=item.get("audit_status", 0),
                    status=item.get("status", 0),
                    file_only_num=str(item.get("file_num", 0)),
                    file_id=item.get("first_fid", 0),
                    file_size=item.get("size", 0),
                    path_info=item.get("path_info", "")
                )
                share_info_list.append(share_info)
            
            # 返回包含分页信息的字典结构
            return {
                "list": share_info_list,
                "metadata": metadata
            }
        
        return []

    async def transfer(self, params: TransferParam, **kwargs: Any) -> bool:
        """
        从各种来源传输文件到自己的网盘
        
        :param params: 转存参数
        :param kwargs: 其他关键字参数
        :return: 转存是否成功
        """
        source_type = params.source_type
        source_id = params.source_id
        source_path = params.source_path
        target_path = params.target_path
        target_id = params.target_id
        file_ids = params.file_ids

        # 合并 params.ext 和 kwargs，params.ext 中的参数优先级更高
        combined_kwargs = {}
        combined_kwargs.update(kwargs)
        if params.ext:
            combined_kwargs.update(params.ext)

        # 确保target_path使用正斜杠
        target_path = target_path.replace("\\", "/")
        
        # self.logger.info(
        #     f"夸克网盘转存请求: source_type='{source_type}', source_id='{source_id}', "
        #     f"source_path='{source_path}', target_path='{target_path}', target_id='{target_id}', file_ids='{file_ids}'"
        # )

        if source_type == "link":
            # 处理分享链接转存
            try:
                # 解析分享链接和密码
                pwd_id, password = _parse_share_url_and_password(source_id)
                
                # 直接使用file_ext中的stoken，避免重新获取导致share_fid_token失效
                stoken = combined_kwargs.get("stoken")
                if not stoken:
                    self.logger.error("转存失败: 未提供stoken，无法进行转存")
                    return False
                
                # self.logger.info(f"使用已有的stoken: {stoken[:20]}...")
                
                # 获取目标目录的file_id
                to_pdir_fid = target_id or combined_kwargs.get("to_pdir_fid")
                
                # 如果没有指定目标file_id，返回错误
                if not to_pdir_fid:
                    self.logger.error(f"转存失败: 目标路径 '{target_path}' 未提供对应的file_id")
                    return False
                
                # 获取分享文件的父目录ID
                pdir_fid = None
                if file_ids and combined_kwargs.get("share_parent_fid"):
                    pdir_fid = combined_kwargs.get("share_parent_fid")
                    self.logger.info(f"使用 share_parent_fid: {pdir_fid}")
                elif combined_kwargs.get("pdir_fid"):
                    pdir_fid = combined_kwargs.get("pdir_fid")
                
                # 如果没有指定分享父目录ID，返回错误
                if not pdir_fid:
                    self.logger.error(f"转存失败: 未能确定分享文件的父目录ID")
                    return False
                
                # 获取share_fid_token列表
                share_fid_tokens = []
                
                # 优先从 files_ext_info 中提取每个文件对应的 share_fid_token
                if combined_kwargs.get("files_ext_info"):
                    files_ext_info = combined_kwargs.get("files_ext_info")
                    # 按照 file_ids 的顺序提取对应的 share_fid_token
                    for file_id in file_ids:
                        token_found = False
                        for file_info in files_ext_info:
                            if file_info.get('file_id') == file_id:
                                file_ext = file_info.get('file_ext', {})
                                share_fid_token = file_ext.get('share_fid_token', '') if isinstance(file_ext, dict) else ''
                                share_fid_tokens.append(share_fid_token)
                                token_found = True
                                break
                        if not token_found:
                            # 如果没有找到对应的文件信息，报错
                            self.logger.error(f"转存失败: 未找到文件 {file_id} 的扩展信息")
                            return False
                elif combined_kwargs.get("share_fid_tokens"):
                    # 如果提供了token列表，直接使用
                    share_fid_tokens = combined_kwargs.get("share_fid_tokens")
                    # 验证token数量是否与文件数量匹配
                    if len(share_fid_tokens) != len(file_ids):
                        self.logger.error(f"转存失败: share_fid_tokens数量({len(share_fid_tokens)})与文件数量({len(file_ids)})不匹配")
                        return False
                elif combined_kwargs.get("share_fid_token"):
                    # 如果提供了单个share_fid_token，为每个文件使用相同的token（通常不推荐）
                    self.logger.warning("使用单个share_fid_token为所有文件转存，可能导致部分文件转存失败")
                    share_fid_tokens = [combined_kwargs.get("share_fid_token")] * len(file_ids)
                else:
                    # 如果没有提供任何token信息，报错
                    self.logger.error("转存失败: 未提供share_fid_token信息，无法进行分享文件转存")
                    return False
                
                #self.logger.info(f"转存参数: to_pdir_fid={to_pdir_fid}, pdir_fid={pdir_fid}")
                #self.logger.info(f"share_fid_tokens: {share_fid_tokens}")
                
                # 调用API保存分享文件
                result = await self._quarkapi.save_shared_files(
                    pwd_id=pwd_id,
                    stoken=stoken,
                    to_pdir_fid=to_pdir_fid,
                    pdir_fid=pdir_fid,
                    pack_dir_name=combined_kwargs.get("pack_dir_name", ""),
                    pdir_save_all=combined_kwargs.get("pdir_save_all", False),
                    scene="link",
                    fid_list=file_ids or [],
                    fid_token_list=share_fid_tokens,
                    exclude_fids=combined_kwargs.get("exclude_fids", [])
                )
                
                # self.logger.info(f"夸克API返回结果: {result}")
                data = result.get("data", {})
                task_id = data.get("task_id")
                
                if task_id:
                    # 查询任务状态
                    # self.logger.info(f"转存任务已创建，任务ID: {task_id}")
                    
                    # 等待任务完成（可选）
                    if combined_kwargs.get("wait_for_completion", False):
                        max_retries = combined_kwargs.get("max_retries", 10)
                        retry_interval = combined_kwargs.get("retry_interval", 2)
                        
                        for i in range(max_retries):
                            try:
                                task_result = await self.query_task(task_id)
                                task_status = task_result.status
                                
                                if task_status == 2:  # 任务完成
                                    # self.logger.info(f"转存任务完成: {task_id}")
                                    return True
                                elif task_status == 3:  # 任务失败
                                    self.logger.error(f"转存任务失败: {task_id}")
                                    return False
                                else:
                                    # 任务进行中，继续等待
                                    self.logger.debug(f"转存任务进行中: {task_id}, 状态: {task_status}")
                                    if i < max_retries - 1:
                                        await asyncio.sleep(retry_interval)
                            except Exception as e:
                                self.logger.warning(f"查询任务状态失败: {e}")
                                if i < max_retries - 1:
                                    await asyncio.sleep(retry_interval)
                        
                        self.logger.warning(f"转存任务超时: {task_id}")
                        return False
                    else:
                        # 不等待任务完成，直接返回成功
                        return True
                else:
                    self.logger.warning("转存API返回成功但没有task_id")
                    return True
                    
            except Exception as e:
                self.logger.error(f"链接分享转存时发生错误: {e}")
                return False

        elif source_type in ["friend", "group"]:
            # TODO: 实现好友和群组分享转存
            self.logger.warning(f"夸克网盘暂不支持 '{source_type}' 类型的转存")
            return False
        else:
            self.logger.error(f"不支持的转存 source_type: {source_type}")
            return False

    async def query_task(self, task_id: str, **kwargs) -> QuarkTask:
        """查询任务状态"""
        try:
            result = await self._quarkapi.query_task(task_id=task_id, **kwargs)
            
            data = result.get("data", {})
            return QuarkTask.from_(data)
        except Exception as e:
            self.logger.error(f"查询任务时发生错误: {e}")
            raise

 