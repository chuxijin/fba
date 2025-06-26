#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.app_auth.model import AppDevice
from backend.plugin.app_auth.schema.device import CreateDeviceParam, UpdateDeviceParam


class CRUDDevice(CRUDPlus[AppDevice]):
    """设备数据库操作类"""

    async def get(self, db: AsyncSession, device_id: int) -> AppDevice | None:
        """
        获取设备详情

        :param db: 数据库会话
        :param device_id: 设备 ID
        :return:
        """
        return await self.select_model(db, device_id)

    async def get_by_device_id(self, db: AsyncSession, device_id: str) -> AppDevice | None:
        """
        通过设备标识获取设备

        :param db: 数据库会话
        :param device_id: 设备标识
        :return:
        """
        return await self.select_model_by_column(db, device_id=device_id)

    async def create(self, db: AsyncSession, obj_in: CreateDeviceParam) -> AppDevice:
        """
        创建设备

        :param db: 数据库会话
        :param obj_in: 创建参数
        :return:
        """
        return await self.create_model(db, obj_in)

    async def update(self, db: AsyncSession, device_id: int, obj_in: UpdateDeviceParam) -> int:
        """
        更新设备

        :param db: 数据库会话
        :param device_id: 设备 ID
        :param obj_in: 更新参数
        :return:
        """
        return await self.update_model(db, device_id, obj_in)

    async def delete(self, db: AsyncSession, device_id: int) -> int:
        """删除设备"""
        return await self.delete_model(db, device_id)

    async def get_list(self, db: AsyncSession, device_name: str = None, status: int = None) -> list[AppDevice]:
        """获取设备列表"""
        stmt = select(self.model)
        if device_name:
            stmt = stmt.where(self.model.device_name.like(f'%{device_name}%'))
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        stmt = stmt.order_by(self.model.created_time.desc())
        return await self.select_models(db, stmt)

    def get_select(self, device_id: str = None, device_name: str = None, status: int = None):
        """获取设备查询语句"""
        stmt = select(self.model)
        if device_id:
            stmt = stmt.where(self.model.device_id.like(f'%{device_id}%'))
        if device_name:
            stmt = stmt.where(self.model.device_name.like(f'%{device_name}%'))
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        stmt = stmt.order_by(self.model.created_time.desc())
        return stmt

    async def update_last_seen(self, db: AsyncSession, device_id: str) -> int:
        """更新设备最后活跃时间"""
        device = await self.get_by_device_id(db, device_id)
        if device:
            from backend.utils.timezone import timezone
            return await self.update_model(db, device.id, {'last_seen': timezone.now()})
        return 0


device_dao: CRUDDevice = CRUDDevice(AppDevice)