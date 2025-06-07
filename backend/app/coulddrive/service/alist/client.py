#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created On: 2024-01-01
@Author: PanMaster团队
Alist 网盘客户端实现
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
import logging
import asyncio

from backend.app.coulddrive.schema.enum import RecursionSpeed
from backend.app.coulddrive.schema.file import BaseFileInfo, ListFilesParam, ListShareFilesParam, MkdirParam, RemoveParam, TransferParam, RelationshipParam, RelationshipType, UserInfoParam
from backend.app.coulddrive.schema.user import (
    BaseUserInfo,
    GetUserFriendDetail,
    GetUserGroupDetail,
)

from backend.app.coulddrive.service.alist.errors import AlistApiError
from backend.app.coulddrive.service.filesync_service import ItemFilter
from backend.app.coulddrive.service.yp_service import BaseDriveClient
from backend.app.coulddrive.service.alist.schemas import (
    AlistFile,
    AlistQuota,
)
from backend.app.coulddrive.service.alist.api import AlistApi
from backend.common.log import log


class AlistClient(BaseDriveClient):
    """Alist 网盘客户端
    
    这是对`AlistApi`的封装。它将原始AlistApi请求的响应内容解析为一些内部数据结构。
    """

    def __init__(
        self,
        cookies: str,
        user_id: Optional[str] = None,
        username: str = "admin",
        password: str = "admin",
    ):
        """
        
        :param cookies: cookies 字符串，格式如 "Authorization: Bearer token"
        :param user_id: 用户ID
        :param username: 用户名，默认为 admin
        :param password: 密码，默认为 admin
        """
        super().__init__()
        # 初始化日志记录器
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 保存登录凭据
        self._username = username
        self._password = password
        
        # 不要先创建空的 AlistApi 实例，直接在 login 中创建
        self._alistapi: AlistApi = None
        self._is_authorized = False

        # 自动登录
        if self.login(cookies, user_id):
            pass
        else:
            raise ValueError("AlistClient 初始化失败：登录失败")

    @property
    def drive_type(self) -> str:
        return "AlistDrive"

    def login(self, cookies: str, user_id: Optional[str] = None) -> bool:
        """
        登录 Alist
        
        :param cookies: cookies 字符串，格式如 "Authorization: Bearer token"
        :param user_id: 用户ID
        :return: 是否登录成功
        """
        # 检查是否有有效的认证信息
        has_cookies = cookies and cookies.strip()
        
        if has_cookies or (self._username and self._password):
            try:
                # 使用用户名密码创建 AlistApi 实例
                self._alistapi = AlistApi(cookies=cookies, username=self._username, password=self._password)
                
                if self._alistapi._cookies or (self._username and self._password):
                    # 通过获取文件列表来验证登录
                    try:
                        async def verify_login():
                            try:
                                result = await self._alistapi.list(file_path="/", page=1, num=1)
                                if isinstance(result, dict) and "content" in result:
                                    return True
                            except Exception:
                                # 如果有用户名密码，尝试重新登录
                                if self._username and self._password:
                                    try:
                                        await self._alistapi.login()
                                        # 重新验证
                                        result = await self._alistapi.list(file_path="/", page=1, num=1)
                                        if isinstance(result, dict) and "content" in result:
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
                self.logger.error(f"AlistApi 初始化失败: {e}")
                self._is_authorized = False
                return False
        
        # 如果没有认证信息且_alistapi为None，返回False
        if self._alistapi is None:
            self._is_authorized = False
            return False
            
        return self._is_authorized

    @property
    def user_id(self) -> Optional[str]:
        """获取用户ID，如果没有则返回None"""
        return None  # Alist 通常不需要用户ID

    @property
    def cookies(self) -> Dict[str, str]:
        return self._alistapi.cookies if self._alistapi else {}

    def get_current_token(self) -> Optional[str]:
        """获取当前有效的 token"""
        return self._alistapi.cookies if self._alistapi else None

    async def quota(self) -> AlistQuota:
        """获取配额信息"""
        # Alist 通常不提供配额信息，返回默认值
        return AlistQuota(quota=0, used=0)

    async def get_user_info(self, params: UserInfoParam = None, **kwargs) -> BaseUserInfo:
        """获取用户信息"""
        try:
            account_info = await self._alistapi.get_account_info()
            
            # 根据 Alist API 返回的数据结构解析
            return BaseUserInfo(
                user_id=str(account_info.get("id", "unknown")),
                username=account_info.get("username", "Unknown User"),
                avatar_url="",  # Alist 通常不提供头像
                is_vip=account_info.get("role", 0) > 1,  # role > 1 可能表示管理员或VIP
                quota=None,  # Alist 通常不在账户信息中提供配额
                used=None
            )
        except Exception as e:
            self.logger.error(f"获取用户信息失败: {e}")
            # 返回默认值
            return BaseUserInfo(
                user_id="alist_user",
                username="Alist User",
                avatar_url="",
                is_vip=False
            )

    async def meta(self, *file_paths: str) -> List[AlistFile]:
        """获取文件元信息"""
        results = []
        for file_path in file_paths:
            try:
                # 获取父目录路径
                parent_path = str(Path(file_path).parent)
                if parent_path == ".":
                    parent_path = "/"
                
                # 获取文件名
                file_name = Path(file_path).name
                
                # 列出父目录内容
                list_result = await self._alistapi.list(file_path=parent_path)
                files = list_result.get("content", [])
                
                # 查找目标文件
                for file_info in files:
                    if file_info.get("name") == file_name:
                        alist_file = AlistFile(
                            name=file_info.get("name", ""),
                            path=file_path,
                            size=file_info.get("size", 0),
                            is_dir=file_info.get("is_dir", False),
                            modified=file_info.get("modified", ""),
                            created=file_info.get("created", ""),
                        )
                        results.append(alist_file)
                        break
            except Exception as e:
                self.logger.error(f"获取文件元信息失败: {file_path}, 错误: {e}")
        
        return results

    async def is_file(self, file_path: str) -> bool:
        """检查是否为文件"""
        try:
            meta_list = await self.meta(file_path)
            return len(meta_list) > 0 and not meta_list[0].is_dir
        except Exception:
            return False

    async def is_dir(self, file_path: str) -> bool:
        """检查是否为目录"""
        try:
            meta_list = await self.meta(file_path)
            return len(meta_list) > 0 and meta_list[0].is_dir
        except Exception:
            return False

    async def get_disk_list(
        self,
        params: ListFilesParam,
        **kwargs: Any
    ) -> List[BaseFileInfo]:
        """
        获取磁盘文件列表
        
        :param params: 列表参数
        :return: 文件信息列表
        """
        try:
            # 获取文件列表
            result = await self._alistapi.list(
                file_path=params.file_path,
                page=1,  # 默认第一页
                num=0,  # 默认100个文件
                refresh=False
            )
            
            # 处理 content 可能为 None 的情况
            files = result.get("content") or []
            if files is None:
                files = []
            
            file_list = []
            
            for file_info in files:
                # 构建完整路径
                file_path = params.file_path.rstrip("/") + "/" + file_info.get("name", "")
                if params.file_path == "/":
                    file_path = "/" + file_info.get("name", "")
                
                base_file_info = BaseFileInfo(
                    file_id=file_info.get("name", ""),  # Alist 使用文件名作为ID
                    file_name=file_info.get("name", ""),
                    file_path=file_path,
                    file_size=file_info.get("size", 0),
                    is_folder=file_info.get("is_dir", False),
                    created_time=file_info.get("created", ""),
                    updated_time=file_info.get("modified", ""),
                    parent_id=params.file_path,
                    drive_type="AlistDrive"
                )
                file_list.append(base_file_info)
            
            return file_list
            
        except Exception as e:
            self.logger.error(f"获取文件列表失败: {e}")
            raise AlistApiError(f"获取文件列表失败: {e}")

    async def mkdir(
        self,
        params: MkdirParam,
        **kwargs: Any,
    ) -> BaseFileInfo:
        """
        创建目录
        
        :param params: 创建目录参数
        :return: 创建的目录信息
        """
        try:
            # 构建完整路径
            if params.parent_id and params.parent_id != "/":
                full_path = params.parent_id.rstrip("/") + "/" + params.file_name
            else:
                full_path = "/" + params.file_name
            
            # 调用 Alist API 创建目录
            result = await self._alistapi.mkdir(path=full_path)
            
            # 返回目录信息
            return BaseFileInfo(
                file_id=params.file_name,
                file_name=params.file_name,
                file_path=full_path,
                file_size=0,
                is_folder=True,
                created_time=datetime.now().isoformat(),
                updated_time=datetime.now().isoformat(),
                parent_id=params.parent_id,
                drive_type="AlistDrive"
            )
            
        except Exception as e:
            self.logger.error(f"创建目录失败: {e}")
            raise AlistApiError(f"创建目录失败: {e}")

    async def remove(
        self,
        params: RemoveParam,
        **kwargs: Any,
    ) -> bool:
        """
        删除文件或目录
        
        :param params: 删除参数
        :return: 是否删除成功
        """
        try:
            # 构建文件名列表
            names = []
            for file_path in params.file_paths:
                file_name = Path(file_path).name
                names.append(file_name)
            
            # 获取父目录路径
            if params.file_paths:
                parent_path = str(Path(params.file_paths[0]).parent)
                if parent_path == ".":
                    parent_path = "/"
            else:
                parent_path = "/"
            
            # 调用删除API
            result = await self._alistapi.remove(names=names, dir=parent_path)
            
            # 检查删除结果
            return True  # Alist API 成功调用即认为删除成功
            
        except Exception as e:
            self.logger.error(f"删除文件失败: {e}")
            return False

    async def transfer(
        self,
        params: TransferParam,
        **kwargs: Any,
    ) -> bool:
        """
        转存文件
        
        :param params: 转存参数
        :return: 是否转存成功
        """
        try:
            # 构建文件名列表
            names = []
            for file_path in params.source_file_paths:
                file_name = Path(file_path).name
                names.append(file_name)
            
            # 获取源目录路径
            if params.source_file_paths:
                src_dir = str(Path(params.source_file_paths[0]).parent)
                if src_dir == ".":
                    src_dir = "/"
            else:
                src_dir = "/"
            
            # 调用复制API
            result = await self._alistapi.copy(
                src_dir=src_dir,
                dst_dir=params.target_parent_path,
                names=names
            )
            
            # 检查复制结果
            return True  # Alist API 成功调用即认为复制成功
            
        except Exception as e:
            self.logger.error(f"转存文件失败: {e}")
            return False

    async def get_share_list(
        self,
        params: ListShareFilesParam,
        **kwargs: Any
    ) -> List[BaseFileInfo]:
        """
        获取分享文件列表
        
        :param params: 分享列表参数
        :return: 分享文件列表
        """
        # Alist 的分享列表和磁盘列表使用同一个接口
        try:
            # 将 ListShareFilesParam 转换为 ListFilesParam
            list_params = ListFilesParam(
                file_path=params.file_path,
                drive_type=params.drive_type
            )
            
            # 使用相同的实现
            return await self.get_disk_list(list_params, **kwargs)
            
        except Exception as e:
            self.logger.error(f"获取分享文件列表失败: {e}")
            return []

    async def get_relationship_list(self, params: RelationshipParam, **kwargs: Any) -> List[Any]:
        """获取关系列表"""
        # Alist 不支持关系功能，返回空列表
        return []
