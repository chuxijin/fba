#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件名: drivebase_service.py
描述: 网盘基础类定义，提供网盘操作的抽象接口和通用实现
作者: PanMaster团队
创建日期: 2023-04-01
最后修改: 2024-04-24
版本: 2.0.0
"""

import time
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

from backend.app.coulddrive.schema.enum import RecursionSpeed, DriveType
from backend.app.coulddrive.schema.file import (
    BaseFileInfo,
    BaseShareInfo,
    CancelShareParam,
    ListFilesParam,
    ListShareFilesParam,
    ListShareInfoParam,
    MkdirParam,
    RelationshipParam,
    RemoveParam,
    ShareParam,
    TransferParam,
    UserInfoParam,
    RenameParam,
)
from backend.app.coulddrive.schema.user import BaseUserInfo, RelationshipItem


class BaseDriveClient:
    """
    网盘客户端基础类
    
    具体的网盘客户端实现应该继承此类
    """

    def __init__(self, *args, **kwargs):
        """
        初始化网盘客户端基类
        :param args: 位置参数
        :param kwargs: 关键字参数
        """
        self._is_authorized = False
        self._last_used = datetime.now()

    @property
    def drive_type(self) -> str:
        """网盘类型"""
        return "unknown"

    @property
    def last_used(self) -> datetime:
        """最后使用时间"""
        return self._last_used

    def update_last_used(self):
        """更新最后使用时间"""
        self._last_used = datetime.now()

    def login(self, *args: Any, **kwargs: Any) -> bool:
        """
        登录网盘
        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: 登录是否成功
        """
        return False
    
    async def get_user_info(self, *args: Any, **kwargs: Any) -> dict:
        """
        获取用户信息
        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: 用户信息字典
        """
        return {}

    async def get_quota(self, *args: Any, **kwargs: Any) -> dict:
        """
        获取网盘空间使用情况

        Args:
            args: 位置参数
            kwargs: 关键字参数

        Returns:
            dict: 包含总空间、已用空间等信息的字典
        """
        return {}
    
    async def get_relationship_list(self, params: RelationshipParam, **kwargs: Any) -> List[Any]:
        """
        获取网盘关系列表
        
        Args:
            params (RelationshipParam): 关系查询参数
            **kwargs: 关键字参数
            
        Returns:
            List[Any]: 关系列表，具体类型取决于 relationship_type
        """
        return []
        
    #--------------------------------------------------
    # 文件和目录管理
    #--------------------------------------------------

    async def mkdir(self, params: MkdirParam, **kwargs: Any) -> BaseFileInfo:
        """创建目录（占位默认实现）"""
        return BaseFileInfo(
            file_id="",
            file_name=params.file_name,
            file_path=params.file_path,
            file_size=0,
            is_folder=True,
            parent_id=params.parent_id or "",
            created_at="",
            updated_at="",
        )

    async def exist(self, fid: str, *args: Any, **kwargs: Any) -> bool:
        """
        检查文件或目录是否存在
        :param fid: 文件或目录ID
        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: 是否存在
        """
        return False

    async def remove(
        self,
        params: RemoveParam,
        **kwargs: Any,
    ) -> bool:
        """
        删除文件或目录
        
        Args:
            file_paths: 要删除的文件或目录的路径，可以是单个路径字符串或路径列表
            file_ids: 要删除的文件或目录的ID，可以是单个ID字符串或ID列表。如果提供，将优先使用ID进行删除
            parent_id: 父目录ID（可选）
            file_name: 文件/目录名称（可选）
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            bool: 删除是否成功
            
        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        return False

    async def move(
        self,
        source_fid: str,
        target_fid: str,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """
        移动文件或目录
        
        将源文件或目录移动到目标目录
        
        参数:
            source_fid (str): 源文件或目录ID
            target_fid (str): 目标目录ID
            args (Any): 位置参数
            kwargs (Any): 关键字参数
            
        返回:
            bool: 移动是否成功
            
        示例:
            >>> drive.move("/源文件.txt", "/目标目录")
            True
        """
        return False

    async def copy(
        self,
        source_fid: str,
        target_fid: str,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """
        复制文件或目录
        
        将源文件或目录复制到目标目录
        
        参数:
            source_fid (str): 源文件或目录ID
            target_fid (str): 目标目录ID
            args (Any): 位置参数
            kwargs (Any): 关键字参数
            
        返回:
            bool: 复制是否成功
            
        示例:
            >>> drive.copy("/源文件.txt", "/目标目录")
            True
        """
        return False

    async def get_disk_list(self, params: ListFilesParam, **kwargs: Any) -> List[BaseFileInfo]:
        """
        获取目录下的文件和目录列表
        
        :param params: 文件列表查询参数
        :param kwargs: 其他关键字参数
        """
        return []
    
    async def get_share_list(self, params: ListShareFilesParam, **kwargs: Any) -> List[BaseFileInfo]:
        """
        获取分享来源的文件列表
        
        :param params: 分享文件列表查询参数
        :param kwargs: 其他关键字参数
        """
        return []
    
    async def get_share_info(self, params: ListShareInfoParam, **kwargs: Any) -> List[BaseShareInfo]:
        """
        获取分享详情列表
        
        :param params: 分享文件列表查询参数
        :param kwargs: 其他关键字参数
        """
        return []

    async def get_item_info(self, fid: str, *args: Any, **kwargs: Any) -> Optional[BaseFileInfo]:
        """获取文件或目录的详细信息"""
        return None
        
    async def rename(self, params: RenameParam, **kwargs: Any) -> bool:
        """重命名文件或目录"""
        raise NotImplementedError("子类必须实现 rename 方法")
        
    async def create_share(self, params: 'ShareParam', **kwargs: Any) -> BaseShareInfo:
        """创建分享链接"""
        return BaseShareInfo(
            title="",
            share_id="",
            pwd_id="",
            url="",
            password="",
            expired_type=0,
            view_count=0,
            expired_at=None,
            expired_left=None,
            audit_status=0,
            status=1,
            file_id=None,
            file_only_num=None,
            file_size=None,
            path_info=None
        )

    async def cancel_share(self, params: 'CancelShareParam', **kwargs: Any) -> bool:
        """取消分享链接"""
        return False

    async def transfer(self, params: TransferParam, **kwargs: Any) -> bool:
        """从各种来源传输文件到自己的网盘"""
        return False
    
    async def search(self, keyword: str, fid: Optional[str] = None, file_type: Optional[str] = None, *args: Any, **kwargs: Any) -> List[BaseFileInfo]:
        """搜索文件或目录"""
        return []
        
    async def get_recycle_list(self, *args: Any, **kwargs: Any) -> List[BaseFileInfo]:
        """获取回收站文件列表"""
        return []

    async def restore(self, fid: str, *args: Any, **kwargs: Any) -> bool:
        """从回收站恢复文件"""
        return False

    async def clear_recycle(self, *args: Any, **kwargs: Any) -> bool:
        """清空回收站"""
        return False


class BaseDrive:
    """
    智能网盘客户端管理器
    
    提供统一的网盘操作接口，自动管理客户端实例的创建、缓存和清理
    """
    
    def __init__(self, cleanup_interval: int = 3600):
        """
        初始化智能网盘管理器
        
        :param cleanup_interval: 清理过期客户端的间隔（秒），默认3600秒（1小时）
        """
        self._clients: Dict[str, BaseDriveClient] = {}
        self._last_cleanup = time.time()
        self._cleanup_interval = cleanup_interval
        # 初始化日志记录器
        import logging
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _get_cache_key(self, drive_type: DriveType, x_token: str) -> str:
        """
        生成缓存键
        
        Args:
            drive_type: 网盘类型
            x_token: 认证令牌
            
        Returns:
            str: 缓存键
        """
        return f"{drive_type.value}:{hash(x_token)}"
    
    def _cleanup_expired_clients(self, max_idle_time: int = 1800):
        """
        清理过期的客户端
        
        :param max_idle_time: 最大空闲时间（秒），默认30分钟
        """
        now = time.time()  # 使用 float 时间戳而不是 datetime
        
        # 检查是否需要执行清理
        if (now - self._last_cleanup) < self._cleanup_interval:
            return
        
        expired_keys = []
        for key, client in self._clients.items():
            if client.last_used:
                # 将 client.last_used (datetime) 转换为时间戳进行比较
                last_used_timestamp = client.last_used.timestamp()
                if (now - last_used_timestamp) > max_idle_time:
                    expired_keys.append(key)
        
        # 移除过期的客户端
        for key in expired_keys:
            self.logger.info(f"清理过期客户端: {key}")
            del self._clients[key]
        
        self._last_cleanup = now
    
    def _get_or_create_client(self, drive_type: DriveType, x_token: str) -> Optional[BaseDriveClient]:
        """
        获取或创建网盘客户端
        
        Args:
            drive_type: 网盘类型
            x_token: 认证令牌
            
        Returns:
            Optional[BaseDriveClient]: 网盘客户端实例
        """
        # 定期清理过期客户端
        self._cleanup_expired_clients()
        
        cache_key = self._get_cache_key(drive_type, x_token)
        
        # 尝试从缓存获取
        if cache_key in self._clients:
            client = self._clients[cache_key]
            client.update_last_used()
            return client
        
        # 创建新客户端
        client = self._create_client(drive_type, x_token)
        if client:
            self._clients[cache_key] = client
        
        return client
    
    def _create_client(self, drive_type: DriveType, x_token: str) -> Optional[BaseDriveClient]:
        """
        创建具体的网盘客户端
        
        Args:
            drive_type: 网盘类型
            x_token: 认证令牌
            
        Returns:
            Optional[BaseDriveClient]: 网盘客户端实例
        """
        try:
            if drive_type in [DriveType.BAIDU, DriveType.BAIDU_DRIVE]:
                return self._create_baidu_client(x_token)
            elif drive_type == DriveType.QUARK_DRIVE:
                return self._create_quark_client(x_token)
            elif drive_type == DriveType.ALIST_DRIVE:
                return self._create_alist_client(x_token)
            else:
                return None
        except Exception as e:
            from backend.common.log import log
            log.error(f"创建网盘客户端失败: {e}")
            return None

    def _create_baidu_client(self, x_token: str) -> Optional[BaseDriveClient]:
        """创建百度网盘客户端"""
        try:
            from .baidu.client import BaiduClient
            return BaiduClient(cookies=x_token)
        except Exception as e:
            from backend.common.log import log
            log.error(f"创建百度网盘客户端失败: {e}")
            return None

    def _create_quark_client(self, x_token: str) -> Optional[BaseDriveClient]:
        """创建夸克网盘客户端"""
        try:
            from .quark.client import QuarkClient
            return QuarkClient(cookies=x_token)
        except Exception as e:
            from backend.common.log import log
            log.error(f"创建夸克网盘客户端失败: {e}", exc_info=True)
            return None

    def _create_alist_client(self, x_token: str) -> Optional[BaseDriveClient]:
        """创建 Alist 网盘客户端"""
        try:
            from .alist.client import AlistClient
            return AlistClient(cookies=x_token)
        except Exception as e:
            from backend.common.log import log
            log.error(f"创建 Alist 网盘客户端失败: {e}", exc_info=True)
            return None
    
    # 旧的具体创建函数已移除，统一通过注册表构造
    
    async def call_method(self, x_token: str, drive_type: Union[str, DriveType], method_name: str, params: Any, **kwargs) -> Any:
        """
        统一的方法调用接口
        
        :param x_token: 认证令牌
        :param drive_type: 网盘类型（字符串或枚举）
        :param method_name: 要调用的方法名
        :param params: 参数对象
        :param kwargs: 额外的关键字参数
        :return: 方法调用结果
        """
        # 如果是枚举类型，转换为字符串
        if isinstance(drive_type, DriveType):
            drive_type_enum = drive_type
        else:
            drive_type_enum = DriveType(drive_type)
        
        # 获取或创建客户端
        client = self._get_or_create_client(
            drive_type=drive_type_enum,
            x_token=x_token
        )
        
        if not client:
            raise ValueError(f"无法创建网盘客户端: {drive_type}")
        
        # 检查方法是否存在
        method = getattr(client, method_name, None)
        if method is None:
            raise AttributeError(f"客户端不支持方法: {method_name}")
        return await method(params, **kwargs)
    
    # 便捷方法（恢复）
    async def get_disk_list(self, x_token: str, params: 'ListFilesParam', **kwargs) -> List[BaseFileInfo]:
        return await self.call_method(x_token, params.drive_type, "get_disk_list", params, **kwargs)

    async def get_user_info(self, x_token: str, params: 'UserInfoParam', **kwargs) -> BaseUserInfo:
        return await self.call_method(x_token, params.drive_type, "get_user_info", params, **kwargs)

    async def get_quota(self, x_token: str, params: 'ListFilesParam', **kwargs) -> dict:
        return await self.call_method(x_token, params.drive_type, "get_quota", params, **kwargs)

    async def get_share_list(self, x_token: str, params: 'ListShareFilesParam', **kwargs) -> List[BaseFileInfo]:
        return await self.call_method(x_token, params.drive_type, "get_share_list", params, **kwargs)

    async def get_share_info(self, x_token: str, params: 'ListShareInfoParam', **kwargs) -> List[BaseShareInfo]:
        return await self.call_method(x_token, params.drive_type, "get_share_info", params, **kwargs)

    async def create_mkdir(self, x_token: str, params: 'MkdirParam', **kwargs) -> BaseFileInfo:
        return await self.call_method(x_token, params.drive_type, "mkdir", params, **kwargs)

    async def remove_files(self, x_token: str, params: 'RemoveParam', **kwargs) -> bool:
        return await self.call_method(x_token, params.drive_type, "remove", params, **kwargs)

    async def transfer_files(self, x_token: str, params: 'TransferParam', **kwargs) -> bool:
        return await self.call_method(x_token, params.drive_type, "transfer", params, **kwargs)

    async def get_relationship_list(self, x_token: str, params: 'RelationshipParam', **kwargs) -> List[RelationshipItem]:
        return await self.call_method(x_token, params.drive_type, "get_relationship_list", params, **kwargs)

    async def create_share(self, x_token: str, params: 'ShareParam', **kwargs) -> BaseShareInfo:
        return await self.call_method(x_token, params.drive_type, "create_share", params, **kwargs)

    async def cancel_share(self, x_token: str, params: 'CancelShareParam', **kwargs) -> bool:
        return await self.call_method(x_token, params.drive_type, "cancel_share", params, **kwargs)
    
    async def rename_files(self, x_token: str, params: 'RenameParam', **kwargs) -> bool:
        """重命名文件或目录"""
        return await self.call_method(x_token, params.drive_type, "rename", params, **kwargs)
    
    def get_client_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有客户端状态
        
        Returns:
            Dict[str, Dict[str, Any]]: 客户端状态信息
        """
        status = {}
        for cache_key, client in self._clients.items():
            status[cache_key] = {
                "drive_type": client.drive_type,
                "last_used": client.last_used.isoformat(),
                "class_name": client.__class__.__name__
            }
        return status
    
    def clear_all_clients(self) -> None:
        """清除所有缓存的客户端"""
        self._clients.clear()


# 全局智能网盘管理器实例
drive_manager = BaseDrive()


def get_drive_manager() -> BaseDrive:
    """获取全局网盘管理器实例"""
    return drive_manager

def validate_drive_config(drive_type: DriveType, config: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    验证网盘配置参数
    
    Args:
        drive_type: 网盘类型
        config: 配置参数
        
    Returns:
        Dict[str, List[str]]: 验证结果，包含 'errors' 和 'warnings' 键
    """
    result = {"errors": [], "warnings": []}
    
    if drive_type in [DriveType.BAIDU, DriveType.BAIDU_DRIVE]:
        # 检查必需参数
        if not config.get("bduss"):
            result["errors"].append("缺少必需参数: bduss")
        
        # 检查可选但推荐的参数
        if not config.get("stoken"):
            result["warnings"].append("建议提供 stoken 参数以获得完整功能")
        
        # 检查参数格式
        bduss = config.get("bduss")
        if bduss and len(bduss) < 10:
            result["warnings"].append("bduss 长度似乎过短，请检查是否正确")
    
    elif drive_type == DriveType.QUARK_DRIVE:
        # 检查必需参数
        if not config.get("cookie"):
            result["errors"].append("缺少必需参数: cookie")
        
        # 检查参数格式
        cookie = config.get("cookie")
        if cookie and not any(key in cookie for key in ["__pus", "__puus"]):
            result["warnings"].append("cookie 中可能缺少关键认证信息，请检查是否包含 __pus 或 __puus")
    
    return result
