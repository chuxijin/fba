#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import Request

from backend.common.exception import errors
from backend.common.security.jwt import superuser_verify
from backend.database.db import async_db_session
from backend.plugin.app_auth.crud import device_dao
from backend.plugin.app_auth.model import AppDevice
from backend.plugin.app_auth.schema.device import CreateDeviceParam, UpdateDeviceParam


class DeviceService:
    """设备服务类"""

    @staticmethod
    async def create(*, request: Request, obj: CreateDeviceParam) -> AppDevice:
        """
        创建设备

        :param request: FastAPI 请求对象
        :param obj: 创建参数
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)
            
            # 检查设备标识是否已存在
            existing_device = await device_dao.get_by_device_id(db, obj.device_id)
            if existing_device:
                raise errors.ForbiddenError(msg='设备标识已存在')
            
            return await device_dao.create(db, obj)

    @staticmethod
    async def register_or_update(device_id: str, device_name: str = None, 
                                device_type: str = None, os_info: str = None, 
                                ip_address: str = None) -> AppDevice:
        """
        注册或更新设备信息

        :param device_id: 设备标识
        :param device_name: 设备名称
        :param device_type: 设备类型
        :param os_info: 操作系统信息
        :param ip_address: IP地址
        :return:
        """
        async with async_db_session.begin() as db:
            # 检查设备是否已存在
            existing_device = await device_dao.get_by_device_id(db, device_id)
            
            if existing_device:
                # 更新设备信息和最后活跃时间
                update_data = {}
                if device_name:
                    update_data['device_name'] = device_name
                if device_type:
                    update_data['device_type'] = device_type
                if os_info:
                    update_data['os_info'] = os_info
                if ip_address:
                    update_data['ip_address'] = ip_address
                
                if update_data:
                    await device_dao.update(db, existing_device.id, update_data)
                
                # 更新最后活跃时间
                await device_dao.update_last_seen(db, device_id)
                return await device_dao.get_by_device_id(db, device_id)
            else:
                # 创建新设备
                device_data = CreateDeviceParam(
                    device_id=device_id,
                    device_name=device_name,
                    device_type=device_type,
                    os_info=os_info,
                    ip_address=ip_address
                )
                return await device_dao.create(db, device_data)

    @staticmethod
    async def update(*, request: Request, device_id: int, obj: UpdateDeviceParam) -> int:
        """
        更新设备

        :param request: FastAPI 请求对象
        :param device_id: 设备 ID
        :param obj: 更新参数
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)
            
            device = await device_dao.get(db, device_id)
            if not device:
                raise errors.NotFoundError(msg='设备不存在')
            
            return await device_dao.update(db, device_id, obj)

    @staticmethod
    async def delete(*, request: Request, device_id: int) -> int:
        """
        删除设备

        :param request: FastAPI 请求对象
        :param device_id: 设备 ID
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)
            
            device = await device_dao.get(db, device_id)
            if not device:
                raise errors.NotFoundError(msg='设备不存在')
            
            return await device_dao.delete(db, device_id)

    @staticmethod
    async def get(device_id: int) -> AppDevice:
        """
        获取设备详情

        :param device_id: 设备 ID
        :return:
        """
        async with async_db_session() as db:
            device = await device_dao.get(db, device_id)
            if not device:
                raise errors.NotFoundError(msg='设备不存在')
            return device

    @staticmethod
    async def get_list(device_name: str = None, status: int = None) -> list[AppDevice]:
        """获取设备列表"""
        async with async_db_session() as db:
            return await device_dao.get_list(db, device_name=device_name, status=status)

    @staticmethod
    def get_select(device_id: str = None, device_name: str = None, status: int = None):
        """获取设备查询语句用于分页"""
        return device_dao.get_select(device_id=device_id, device_name=device_name, status=status)

    @staticmethod
    async def get_options() -> list[dict]:
        """获取设备选择选项"""
        async with async_db_session() as db:
            devices = await device_dao.get_list(db, status=1)  # 只获取启用的设备
            return [
                {
                    'label': f"{device.device_name or device.device_id} ({device.device_type or '未知类型'})",
                    'value': device.id
                }
                for device in devices
            ]


device_service = DeviceService()