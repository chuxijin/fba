#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

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
from backend.common.log import log


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
            log.info(f"✅ 已注册驱动: {drive_type.value} -> {driver_class.__name__}")
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
# 第四部分：网盘服务统一接口 - 双模式架构
# ============================================================

class CouldDriveService:
    """
    网盘服务统一接口 - 双模式架构

    重构自 yp_service.BaseDrive 和 AuthenticatedDriveManager
    用一个类实现两种调用模式

    【模式1 - 外部调用】方便灵活，适合第三方集成
    - 直接传入认证信息（cookies/auth_data）
    - 明确指定驱动类型
    - 不依赖数据库

    使用示例：
        service = CouldDriveService(
            auth_data=cookies,
            drive_type=DriveType.QUARK
        )
        files = await service.get_disk_list(fid="0")

    【模式2 - 内部调用】安全便捷，适合内部业务逻辑
    - 传入数据库会话 + 用户ID
    - 自动查询用户认证信息
    - 自动获取驱动类型
    - 认证信息不暴露

    使用示例：
        service = CouldDriveService(db=db, user_id=123)
        files = await service.get_disk_list(fid="0")

    架构特点：
    1. 统一管理驱动实例（客户端缓存）
    2. 自动清理过期客户端
    3. 懒加载用户信息（内部模式）
    4. 支持所有网盘驱动（通过 DriverRegistry）
    """

    def __init__(
        self,
        *,
        auth_data: Optional[Union[str, Dict[str, Any]]] = None,
        drive_type: Optional[DriveType] = None,
        db: Optional[AsyncSession] = None,
        user_id: Optional[int] = None,
        current_user_id: Optional[int] = None,
        cleanup_interval: int = 3600
    ):
        """
        初始化网盘服务

        :param auth_data: 认证数据（外部模式必需）
        :param drive_type: 驱动类型（外部模式必需）
        :param db: 数据库会话（内部模式必需）
        :param user_id: 用户ID（内部模式必需，指网盘账户ID）
        :param current_user_id: 当前登录用户ID（内部模式可选，用于权限校验）
        :param cleanup_interval: 清理过期客户端的间隔（秒）
        """
        # ========== 模式检测与验证 ==========
        external_mode = auth_data is not None and drive_type is not None
        internal_mode = db is not None and user_id is not None

        if external_mode and internal_mode:
            raise ValueError("不能同时使用外部模式和内部模式")

        if not external_mode and not internal_mode:
            raise ValueError("必须选择一种模式：外部模式(auth_data+drive_type) 或 内部模式(db+user_id)")

        # ========== 外部模式 ==========
        self._external_mode = external_mode
        self._auth_data = auth_data
        self._drive_type = drive_type

        # ========== 内部模式 ==========
        self._internal_mode = internal_mode
        self._db = db
        self._user_id = user_id
        self._current_user_id = current_user_id
        self._user_cache: Optional[Any] = None  # 懒加载用户信息缓存

        # ========== 驱动实例管理 ==========
        self._clients: Dict[str, BaseDriveClient] = {}
        self._last_cleanup = time.time()
        self._cleanup_interval = cleanup_interval

    async def get_drive_type(self) -> DriveType:
        """
        获取当前驱动类型

        :return: 驱动类型
        """
        _, drive_type = await self._ensure_auth_info()
        return drive_type

    async def _ensure_auth_info(self) -> tuple[Union[str, Dict[str, Any]], DriveType]:
        """
        获取认证信息（内部方法）

        :return: (auth_data, drive_type) 元组
        """
        if self._external_mode:
            # 确保 drive_type 是枚举类型
            if isinstance(self._drive_type, str):
                drive_type_enum = DriveType(self._drive_type)
            else:
                drive_type_enum = self._drive_type
            return self._auth_data, drive_type_enum

        if self._user_cache is None:
            from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao

            self._user_cache = await drive_account_dao.get(self._db, self._user_id)
            if not self._user_cache:
                raise ValueError(f"网盘用户不存在: {self._user_id}")

            # 🔐 权限校验：如果传了 current_user_id，则校验所有权
            if self._current_user_id and self._user_cache.user_id != self._current_user_id:
                raise PermissionError(f"无权访问网盘账户: {self._user_id}")

        return self._user_cache.cookies, DriveType(self._user_cache.type)

    def _get_cache_key(self, drive_type: Union[str, DriveType], auth_data: Union[str, Dict[str, Any]]) -> str:
        """生成缓存键"""
        if isinstance(auth_data, str):
            data_str = auth_data
        else:
            data_str = json.dumps(auth_data, sort_keys=True)

        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]

        # 处理 drive_type 可能是字符串或枚举的情况
        if isinstance(drive_type, str):
            drive_type_str = drive_type
        else:
            drive_type_str = drive_type.value

        return f"{drive_type_str}:{data_hash}"

    def _cleanup_expired_clients(self, max_idle_time: int = 1800):
        """清理过期的客户端"""
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
            log.info(f"清理过期客户端: {key}")
            del self._clients[key]

        self._last_cleanup = now

    async def _get_or_create_client(
        self,
        drive_type: Union[str, DriveType],
        auth_data: Union[str, Dict[str, Any]]
    ) -> Optional[BaseDriveClient]:
        """获取或创建驱动实例"""
        self._cleanup_expired_clients()

        cache_key = self._get_cache_key(drive_type, auth_data)

        if cache_key in self._clients:
            client = self._clients[cache_key]
            client.update_last_used()
            return client

        # 确保 drive_type 是枚举类型
        if isinstance(drive_type, str):
            drive_type_enum = DriveType(drive_type)
        else:
            drive_type_enum = drive_type

        driver_class = DriverRegistry.get_driver_class(drive_type_enum)
        if not driver_class:
            log.error(f"未注册的驱动类型: {drive_type}")
            return None

        try:
            client = driver_class(config=auth_data)
            self._clients[cache_key] = client
            return client
        except Exception as e:
            log.error(f"创建驱动实例失败: {e}", exc_info=True)
            return None

    # ========================================================
    # 【工厂方法】- 从请求自动创建服务
    # ========================================================

    @classmethod
    def create_from_request(
        cls,
        db: AsyncSession,
        request: Any,
        x_token: str,
        drive_type: DriveType,
        drive_account_id: Optional[int] = None
    ) -> CouldDriveService:
        """
        从请求自动创建服务实例（自动判断模式）

        :param db: 数据库会话
        :param request: 请求对象（包含 request.user）
        :param x_token: 认证令牌
        :param drive_type: 驱动类型
        :param drive_account_id: 网盘账户ID（可选）
        :return: 服务实例
        """
        if drive_account_id:
            # 内部模式：带权限校验
            return cls(
                db=db,
                user_id=drive_account_id,
                current_user_id=request.user.id
            )
        else:
            # 外部模式：调试用
            return cls(
                auth_data=x_token,
                drive_type=drive_type
            )

    # ========================================================
    # 【核心调用方法】- 统一调用接口
    # ========================================================

    async def call_method(
        self,
        method_name: str,
        params: Any,
        **kwargs
    ) -> Any:
        """
        统一方法调用接口

        :param method_name: 方法名
        :param params: 参数对象
        :param kwargs: 额外参数
        :return: 方法调用结果
        """
        auth_data, drive_type = await self._ensure_auth_info()

        client = await self._get_or_create_client(drive_type, auth_data)
        if not client:
            raise ValueError(f"无法创建驱动客户端: {drive_type}")

        method = getattr(client, method_name, None)
        if method is None:
            raise AttributeError(f"驱动 {client.__class__.__name__} 不支持方法: {method_name}")

        return await method(params, **kwargs)

    # ========================================================
    # 【便捷方法】- 常用功能封装
    # ========================================================

    async def get_user_info(self, params: UserInfoParam, **kwargs) -> BaseUserInfo:
        """获取用户信息"""
        auth_data, drive_type = await self._ensure_auth_info()
        params.drive_type = drive_type
        return await self.call_method("get_user_info", params, **kwargs)

    async def get_disk_list(self, params: ListFilesParam, **kwargs) -> List[BaseFileInfo]:
        """
        列出文件

        :param params: 查询参数
        :return: 文件列表
        """
        auth_data, drive_type = await self._ensure_auth_info()
        params.drive_type = drive_type
        return await self.call_method("get_disk_list", params, **kwargs)

    async def get_share_info(self, params: ListShareInfoParam, **kwargs) -> Union[List[BaseShareInfo], Dict[str, Any]]:
        """
        获取分享信息

        :param params: 查询参数
        :return: 分享信息列表
        """
        auth_data, drive_type = await self._ensure_auth_info()
        params.drive_type = drive_type
        return await self.call_method("get_share_info", params, **kwargs)

    async def get_share_list(self, params: ListShareFilesParam, **kwargs) -> List[BaseFileInfo]:
        """
        获取分享文件列表

        :param params: 查询参数
        :return: 文件列表
        """
        auth_data, drive_type = await self._ensure_auth_info()
        params.drive_type = drive_type
        return await self.call_method("get_share_list", params, **kwargs)

    async def create_share(self, params: ShareParam, **kwargs) -> BaseShareInfo:
        """
        创建分享

        :param params: 分享参数
        :return: 分享信息
        """
        auth_data, drive_type = await self._ensure_auth_info()
        params.drive_type = drive_type
        return await self.call_method("create_share", params, **kwargs)

    async def cancel_share(self, params: CancelShareParam, **kwargs) -> bool:
        """
        取消分享

        :param params: 取消分享参数
        :return: 是否成功
        """
        auth_data, drive_type = await self._ensure_auth_info()
        params.drive_type = drive_type
        return await self.call_method("cancel_share", params, **kwargs)

    async def transfer_files(self, params: TransferParam, **kwargs) -> bool:
        """
        转存文件

        :param params: 转存参数
        :return: 是否成功
        """
        auth_data, drive_type = await self._ensure_auth_info()
        params.drive_type = drive_type
        return await self.call_method("transfer", params, **kwargs)

    async def mkdir(self, params: MkdirParam, **kwargs) -> BaseFileInfo:
        """
        创建文件夹

        :param params: 创建文件夹参数
        :return: 文件信息
        """
        auth_data, drive_type = await self._ensure_auth_info()
        params.drive_type = drive_type
        return await self.call_method("mkdir", params, **kwargs)

    async def rename(self, params: RenameParam, **kwargs) -> bool:
        """
        重命名文件

        :param params: 重命名参数
        :return: 是否成功
        """
        auth_data, drive_type = await self._ensure_auth_info()
        params.drive_type = drive_type
        return await self.call_method("rename", params, **kwargs)

    async def move(self, params: MoveParam, **kwargs) -> bool:
        """
        移动文件

        :param params: 移动参数
        :return: 是否成功
        """
        auth_data, drive_type = await self._ensure_auth_info()
        params.drive_type = drive_type
        return await self.call_method("move", params, **kwargs)

    async def copy(self, params: CopyParam, **kwargs) -> bool:
        """
        复制文件

        :param params: 复制参数
        :return: 是否成功
        """
        auth_data, drive_type = await self._ensure_auth_info()
        params.drive_type = drive_type
        return await self.call_method("copy", params, **kwargs)

    async def remove(self, params: RemoveParam, **kwargs) -> bool:
        """
        删除文件

        :param params: 删除参数
        :return: 是否成功
        """
        auth_data, drive_type = await self._ensure_auth_info()
        params.drive_type = drive_type
        return await self.call_method("remove", params, **kwargs)


# ========================================================
# 【工厂函数】- 便捷创建实例
# ========================================================

def create_external_drive_service(
    auth_data: Union[str, Dict[str, Any]],
    drive_type: DriveType
) -> CouldDriveService:
    """
    创建外部模式服务实例

    :param auth_data: 认证数据
    :param drive_type: 驱动类型
    :return: 服务实例
    """
    return CouldDriveService(auth_data=auth_data, drive_type=drive_type)


def create_internal_drive_service(
    db: AsyncSession,
    user_id: int,
    current_user_id: Optional[int] = None
) -> CouldDriveService:
    """
    创建内部模式服务实例

    :param db: 数据库会话
    :param user_id: 网盘账户ID
    :param current_user_id: 当前登录用户ID（可选，用于权限校验）
    :return: 服务实例
    """
    return CouldDriveService(db=db, user_id=user_id, current_user_id=current_user_id)


# ============================================================
# 驱动自动注册（导入驱动模块触发装饰器）
# ============================================================

# 导入所有驱动模块，触发 @DriverRegistry.register() 装饰器
from backend.app.coulddrive.service.baidu.client import BaiduClient  # noqa: F401, E402
from backend.app.coulddrive.service.quark.client import QuarkClient  # noqa: F401, E402
from backend.app.coulddrive.service.alist.client import AlistClient  # noqa: F401, E402
