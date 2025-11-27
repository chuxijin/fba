#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网盘统一服务 - Alist 风格架构

架构特点：
1. 驱动注册表机制 - 零修改扩展新网盘
2. 多认证方式支持 - Cookie、OAuth、官方 API 等
3. 驱动自描述配置 - 前端可动态生成表单
4. 完全向后兼容 - 支持现有 Cookie 方式

作者: PanMaster团队
版本: 3.0.0 (Alist 风格重构)
"""

import hashlib
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel

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
    RemoveParam,
    RenameParam,
    ShareParam,
    TransferParam,
    UserInfoParam,
)
from backend.app.coulddrive.schema.user import BaseUserInfo, RelationshipItem


# ============================================================
# 第一部分：配置项定义（学习 Alist Items）
# ============================================================

class ConfigItemType:
    """配置项类型常量"""

    STRING = "string"
    SELECT = "select"
    BOOL = "bool"
    NUMBER = "number"
    PASSWORD = "password"


class ConfigItem(BaseModel):
    """
    驱动配置项定义 - Alist 风格

    用于驱动声明需要的配置参数，前端可根据此动态生成表单
    """

    name: str
    label: str
    type: str = ConfigItemType.STRING
    required: bool = True
    default: Optional[Any] = None
    options: Optional[List[str]] = None
    description: Optional[str] = None
    placeholder: Optional[str] = None


# ============================================================
# 第二部分：驱动注册表（学习 Alist RegisterDriver）
# ============================================================

class DriverRegistry:
    """
    驱动注册表 - Alist 核心机制

    功能：
    1. 自动注册驱动类
    2. 根据 drive_type 获取驱动类
    3. 零修改扩展新网盘

    使用方式：
        @DriverRegistry.register(DriveType.BAIDU_DRIVE)
        class BaiduClient(BaseDriveClient):
            pass
    """

    _drivers: Dict[DriveType, Type['BaseDriveClient']] = {}

    @classmethod
    def register(cls, drive_type: DriveType):
        """
        装饰器：自动注册驱动

        :param drive_type: 驱动类型枚举
        """
        def decorator(driver_class: Type['BaseDriveClient']):
            cls._drivers[drive_type] = driver_class
            import logging
            logging.getLogger(__name__).info(
                f"✅ 已注册驱动: {drive_type.value} -> {driver_class.__name__}"
            )
            return driver_class

        return decorator

    @classmethod
    def get_driver_class(cls, drive_type: DriveType) -> Optional[Type['BaseDriveClient']]:
        """
        根据驱动类型获取驱动类

        :param drive_type: 驱动类型
        :return: 驱动类，如果未注册则返回 None
        """
        return cls._drivers.get(drive_type)

    @classmethod
    def get_all_drivers(cls) -> Dict[DriveType, Type['BaseDriveClient']]:
        """获取所有已注册的驱动"""
        return cls._drivers.copy()


# ============================================================
# 第三部分：驱动基类（学习 Alist Driver Interface）
# ============================================================

class BaseDriveClient(ABC):
    """
    网盘驱动基类 - Alist 风格

    特点：
    1. ABC 抽象基类，强制子类实现关键方法
    2. 支持多种认证方式（Cookie、OAuth等）
    3. 驱动自描述配置（get_config_items）
    4. 向后兼容 Cookie 字符串

    认证方式：
    - 传入 str：Cookie 字符串（向后兼容）
    - 传入 dict：配置字典（支持多种认证）
    """

    def __init__(self, config: Union[str, Dict[str, Any]], **kwargs):
        """
        初始化驱动

        :param config: 认证配置
            - str: cookie 字符串（向后兼容）
            - dict: 配置字典 {"refresh_token": "xxx", ...}
        """
        # 向后兼容：自动转换 cookie 字符串为配置字典
        if isinstance(config, str):
            self.config = self._convert_cookie_to_config(config)
        else:
            self.config = config

        self._is_authorized = False
        self._last_used = datetime.now()

    def _convert_cookie_to_config(self, cookies: str) -> Dict[str, Any]:
        """
        将 cookie 字符串转换为配置字典（向后兼容）

        子类可以重写这个方法来自定义转换逻辑

        :param cookies: cookie 字符串
        :return: 配置字典
        """
        return {"cookie": cookies}

    # ========== 驱动属性 ==========

    @property
    @abstractmethod
    def drive_type(self) -> str:
        """驱动类型标识"""
        pass

    @property
    def last_used(self) -> datetime:
        """最后使用时间"""
        return self._last_used

    def update_last_used(self):
        """更新最后使用时间"""
        self._last_used = datetime.now()

    # ========== 配置相关（Alist 风格）==========

    @classmethod
    @abstractmethod
    def get_config_items(cls) -> List[ConfigItem]:
        """
        声明驱动需要的配置项 - Alist Items() 机制

        每个驱动自己声明需要什么配置，前端可根据此动态生成表单

        示例：
        百度网盘（Cookie 方式）：
            return [
                ConfigItem(name="cookie", label="Cookie", required=True),
            ]

        阿里云盘（官方 API 方式）：
            return [
                ConfigItem(name="refresh_token", label="刷新令牌", required=True),
                ConfigItem(name="client_id", label="客户端ID", required=False),
            ]
        """
        pass

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        验证配置（基于 get_config_items）

        自动根据 get_config_items() 验证配置
        子类可以重写进行额外验证

        :param config: 配置字典
        :return: {"errors": [], "warnings": []}
        """
        result = {"errors": [], "warnings": []}

        config_items = cls.get_config_items()

        # 检查必需字段
        for item in config_items:
            if item.required and not config.get(item.name):
                result["errors"].append(f"缺少必需参数: {item.label or item.name}")

        return result

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        :param key: 配置键名
        :param default: 默认值
        :return: 配置值
        """
        return self.config.get(key, default)

    # ========== 抽象方法：驱动必须实现 ==========

    @abstractmethod
    async def get_user_info(self, params: UserInfoParam, **kwargs) -> BaseUserInfo:
        """获取用户信息"""
        pass

    @abstractmethod
    async def get_disk_list(self, params: ListFilesParam, **kwargs) -> List[BaseFileInfo]:
        """列出文件"""
        pass

    @abstractmethod
    async def mkdir(self, params: MkdirParam, **kwargs) -> BaseFileInfo:
        """创建目录"""
        pass

    @abstractmethod
    async def remove(self, params: RemoveParam, **kwargs) -> bool:
        """删除文件"""
        pass

    @abstractmethod
    async def rename(self, params: RenameParam, **kwargs) -> bool:
        """重命名"""
        pass

    @abstractmethod
    async def move(self, params: MoveParam, **kwargs) -> bool:
        """移动"""
        pass

    @abstractmethod
    async def copy(self, params: CopyParam, **kwargs) -> bool:
        """复制"""
        pass

    # ========== 可选方法（子类可选实现）==========

    async def get_quota(self, params: Any, **kwargs) -> dict:
        """获取网盘空间使用情况（可选实现）"""
        return {}

    async def get_share_list(self, params: ListShareFilesParam, **kwargs) -> List[BaseFileInfo]:
        """获取分享文件列表（可选实现）"""
        return []

    async def get_share_info(self, params: ListShareInfoParam, **kwargs) -> List[BaseShareInfo]:
        """获取分享详情列表（可选实现）"""
        return []

    async def create_share(self, params: ShareParam, **kwargs) -> BaseShareInfo:
        """创建分享链接（可选实现）"""
        raise NotImplementedError(f"{self.__class__.__name__} 不支持创建分享")

    async def cancel_share(self, params: CancelShareParam, **kwargs) -> bool:
        """取消分享链接（可选实现）"""
        raise NotImplementedError(f"{self.__class__.__name__} 不支持取消分享")

    async def transfer(self, params: TransferParam, **kwargs) -> bool:
        """转存文件（可选实现）"""
        raise NotImplementedError(f"{self.__class__.__name__} 不支持转存")

    async def get_relationship_list(self, params: RelationshipParam, **kwargs) -> List[RelationshipItem]:
        """获取关系列表（可选实现）"""
        return []

    async def exist(self, fid: str, **kwargs) -> bool:
        """检查文件是否存在（可选实现）"""
        return False

    async def get_item_info(self, fid: str, **kwargs) -> Optional[BaseFileInfo]:
        """获取文件详细信息（可选实现）"""
        return None

    async def search(self, keyword: str, fid: Optional[str] = None, file_type: Optional[str] = None, **kwargs) -> List[BaseFileInfo]:
        """搜索文件（可选实现）"""
        return []

    async def get_recycle_list(self, **kwargs) -> List[BaseFileInfo]:
        """获取回收站列表（可选实现）"""
        return []

    async def restore(self, fid: str, **kwargs) -> bool:
        """从回收站恢复（可选实现）"""
        return False

    async def clear_recycle(self, **kwargs) -> bool:
        """清空回收站（可选实现）"""
        return False


# ============================================================
# 第四部分：驱动管理器（学习 Alist FS 层）
# ============================================================

class BaseDrive:
    """
    驱动管理器 - Alist FS 层

    职责：
    1. 管理驱动实例的生命周期
    2. 提供统一调用接口（call_method）
    3. 实现客户端缓存
    4. 支持多种认证方式
    """

    def __init__(self, cleanup_interval: int = 3600):
        """
        初始化驱动管理器

        :param cleanup_interval: 清理过期客户端的间隔（秒）
        """
        self._clients: Dict[str, BaseDriveClient] = {}
        self._last_cleanup = time.time()
        self._cleanup_interval = cleanup_interval

        import logging
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_cache_key(self, drive_type: DriveType, auth_data: Union[str, Dict[str, Any]]) -> str:
        """
        生成缓存键 - 支持多种认证方式

        :param drive_type: 驱动类型
        :param auth_data: 认证数据（str 或 dict）
        :return: 缓存键
        """
        # 统一转换为字符串进行哈希
        if isinstance(auth_data, str):
            data_str = auth_data
        else:
            # 字典转 JSON 字符串（排序键保证一致性）
            data_str = json.dumps(auth_data, sort_keys=True)

        # 使用 SHA256 而不是 hash()，更安全
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]
        return f"{drive_type.value}:{data_hash}"

    def _cleanup_expired_clients(self, max_idle_time: int = 1800):
        """
        清理过期的客户端

        :param max_idle_time: 最大空闲时间（秒），默认 30 分钟
        """
        now = time.time()

        if (now - self._last_cleanup) < self._cleanup_interval:
            return

        expired_keys = []
        for key, client in self._clients.items():
            if client.last_used:
                last_used_timestamp = client.last_used.timestamp()
                if (now - last_used_timestamp) > max_idle_time:
                    expired_keys.append(key)

        for key in expired_keys:
            self.logger.info(f"清理过期客户端: {key}")
            del self._clients[key]

        self._last_cleanup = now

    def _get_or_create_client(
        self,
        drive_type: DriveType,
        auth_data: Union[str, Dict[str, Any]]
    ) -> Optional[BaseDriveClient]:
        """
        获取或创建驱动实例 - 使用注册表

        :param drive_type: 驱动类型
        :param auth_data: 认证数据
            - str: cookie 字符串（向后兼容）
            - dict: 配置字典（支持多种认证）
        :return: 驱动实例
        """
        # 清理过期客户端
        self._cleanup_expired_clients()

        cache_key = self._get_cache_key(drive_type, auth_data)

        # 尝试从缓存获取
        if cache_key in self._clients:
            client = self._clients[cache_key]
            client.update_last_used()
            return client

        # ========== 关键：使用注册表创建 ==========
        driver_class = DriverRegistry.get_driver_class(drive_type)
        if not driver_class:
            self.logger.error(f"未注册的驱动类型: {drive_type}")
            return None

        try:
            # 创建新实例（智能处理 str 或 dict）
            client = driver_class(config=auth_data)
            self._clients[cache_key] = client
            return client
        except Exception as e:
            from backend.common.log import log
            log.error(f"创建驱动实例失败: {e}", exc_info=True)
            return None

    # ========== 统一调用接口（Alist 风格）==========

    async def call_method(
        self,
        auth_data: Union[str, Dict[str, Any]],
        drive_type: Union[str, DriveType],
        method_name: str,
        params: Any,
        **kwargs
    ) -> Any:
        """
        统一方法调用接口 - Alist FS 层风格

        这是唯一对外的调用入口！

        :param auth_data: 认证数据
            - 旧方式：x_token (cookie 字符串)
            - 新方式：配置字典 {"refresh_token": "xxx", ...}
        :param drive_type: 驱动类型（字符串或枚举）
        :param method_name: 方法名（如 "get_disk_list"）
        :param params: 参数对象
        :param kwargs: 额外参数
        :return: 方法调用结果
        """
        # 类型转换
        if isinstance(drive_type, str):
            drive_type = DriveType(drive_type)

        # 获取客户端
        client = self._get_or_create_client(drive_type, auth_data)
        if not client:
            raise ValueError(f"无法创建驱动客户端: {drive_type}")

        # 检查方法是否存在
        method = getattr(client, method_name, None)
        if method is None:
            raise AttributeError(f"驱动 {client.__class__.__name__} 不支持方法: {method_name}")

        # 调用方法
        return await method(params, **kwargs)

    # ========== 工具方法 ==========

    def get_client_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有客户端状态"""
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

    # ========== 便捷方法（向后兼容）==========

    async def get_disk_list(
        self,
        auth_data: Union[str, Dict[str, Any]],
        params: ListFilesParam,
        **kwargs
    ) -> List[BaseFileInfo]:
        """获取文件列表"""
        return await self.call_method(auth_data, params.drive_type, "get_disk_list", params, **kwargs)

    async def get_share_list(
        self,
        auth_data: Union[str, Dict[str, Any]],
        params: ListShareFilesParam,
        **kwargs
    ) -> List[BaseFileInfo]:
        """获取分享文件列表"""
        return await self.call_method(auth_data, params.drive_type, "get_share_list", params, **kwargs)

    async def get_share_info(
        self,
        auth_data: Union[str, Dict[str, Any]],
        params: ListShareInfoParam,
        **kwargs
    ) -> Union[List[BaseShareInfo], Dict[str, Any]]:
        """获取分享详情"""
        return await self.call_method(auth_data, params.drive_type, "get_share_info", params, **kwargs)

    async def create_mkdir(
        self,
        auth_data: Union[str, Dict[str, Any]],
        params: MkdirParam,
        **kwargs
    ) -> BaseFileInfo:
        """创建目录"""
        return await self.call_method(auth_data, params.drive_type, "mkdir", params, **kwargs)

    async def rename_files(
        self,
        auth_data: Union[str, Dict[str, Any]],
        params: RenameParam,
        **kwargs
    ) -> bool:
        """重命名文件"""
        return await self.call_method(auth_data, params.drive_type, "rename", params, **kwargs)

    async def move_files(
        self,
        auth_data: Union[str, Dict[str, Any]],
        params: MoveParam,
        **kwargs
    ) -> bool:
        """移动文件"""
        return await self.call_method(auth_data, params.drive_type, "move", params, **kwargs)

    async def copy_files(
        self,
        auth_data: Union[str, Dict[str, Any]],
        params: CopyParam,
        **kwargs
    ) -> bool:
        """复制文件"""
        return await self.call_method(auth_data, params.drive_type, "copy", params, **kwargs)

    async def remove_files(
        self,
        auth_data: Union[str, Dict[str, Any]],
        params: RemoveParam,
        **kwargs
    ) -> bool:
        """删除文件"""
        return await self.call_method(auth_data, params.drive_type, "remove", params, **kwargs)

    async def transfer_files(
        self,
        auth_data: Union[str, Dict[str, Any]],
        params: TransferParam,
        **kwargs
    ) -> bool:
        """转存文件"""
        return await self.call_method(auth_data, params.drive_type, "transfer", params, **kwargs)

    async def create_share(
        self,
        auth_data: Union[str, Dict[str, Any]],
        params: ShareParam,
        **kwargs
    ) -> BaseShareInfo:
        """创建分享"""
        return await self.call_method(auth_data, params.drive_type, "create_share", params, **kwargs)

    async def cancel_share(
        self,
        auth_data: Union[str, Dict[str, Any]],
        params: CancelShareParam,
        **kwargs
    ) -> bool:
        """取消分享"""
        return await self.call_method(auth_data, params.drive_type, "cancel_share", params, **kwargs)

    async def get_user_info(
        self,
        auth_data: Union[str, Dict[str, Any]],
        params: UserInfoParam,
        **kwargs
    ) -> BaseUserInfo:
        """获取用户信息"""
        return await self.call_method(auth_data, params.drive_type, "get_user_info", params, **kwargs)

    async def get_relationship_list(
        self,
        auth_data: Union[str, Dict[str, Any]],
        params: RelationshipParam,
        **kwargs
    ) -> List[RelationshipItem]:
        """获取关系列表"""
        return await self.call_method(auth_data, params.drive_type, "get_relationship_list", params, **kwargs)


# ============================================================
# 全局实例
# ============================================================

drive_manager = BaseDrive()


def get_drive_manager() -> BaseDrive:
    """获取全局驱动管理器实例"""
    return drive_manager


# ============================================================
# 驱动自动注册（导入驱动模块触发装饰器）
# ============================================================

# 导入所有驱动模块，触发 @DriverRegistry.register() 装饰器
# 这些导入必须放在 drive_manager 实例创建之后
from backend.app.coulddrive.service.baidu.client import BaiduClient  # noqa: F401, E402
from backend.app.coulddrive.service.quark.client import QuarkClient  # noqa: F401, E402
from backend.app.coulddrive.service.alist.client import AlistClient  # noqa: F401, E402
