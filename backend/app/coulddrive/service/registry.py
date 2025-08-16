#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网盘客户端注册表与注册装饰器
"""

from __future__ import annotations

from typing import Callable, Dict, TYPE_CHECKING

from backend.app.coulddrive.schema.enum import DriveType

if TYPE_CHECKING:
    # 仅用于类型检查，避免运行时循环引用
    from .yp_service import BaseDriveClient


# 运行时注册表：DriveType -> 构造器
DRIVE_CLIENT_REGISTRY: Dict[DriveType, Callable[[str], 'BaseDriveClient']] = {}


def register_drive_client(drive_type: DriveType) -> Callable[[Callable[[str], 'BaseDriveClient']], Callable[[str], 'BaseDriveClient']]:
    """注册网盘客户端构造器

    :param drive_type: 网盘类型
    :return: 装饰后的构造器
    """

    def decorator(ctor: Callable[[str], 'BaseDriveClient']) -> Callable[[str], 'BaseDriveClient']:
        DRIVE_CLIENT_REGISTRY[drive_type] = ctor
        return ctor

    return decorator


def get_registered_drive_types() -> list[DriveType]:
    """获取已注册的网盘类型列表"""
    return list(DRIVE_CLIENT_REGISTRY.keys())


