#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.model import JiaDevice
from backend.app.jia.schema import DeviceRegisterParam, DeviceUpdateParam
from backend.utils.timezone import timezone


class CRUDDevice:
    """设备 CRUD 操作"""

    async def get_by_id(self, db: AsyncSession, device_id: int) -> JiaDevice | None:
        """根据 ID 获取设备"""
        return await db.get(JiaDevice, device_id)

    async def get_by_token(self, db: AsyncSession, fcm_token: str) -> JiaDevice | None:
        """根据 FCM Token 获取设备"""
        stmt = select(JiaDevice).where(JiaDevice.fcm_token == fcm_token)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_and_device(
        self, db: AsyncSession, user_id: int, device_id: str
    ) -> JiaDevice | None:
        """根据用户 ID 和设备 ID 获取设备"""
        stmt = select(JiaDevice).where(
            JiaDevice.user_id == user_id,
            JiaDevice.device_id == device_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, db: AsyncSession, user_id: int) -> list[JiaDevice]:
        """获取用户的所有设备"""
        stmt = select(JiaDevice).where(
            JiaDevice.user_id == user_id,
            JiaDevice.is_active.is_(True),
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_all_active(self, db: AsyncSession) -> list[JiaDevice]:
        """获取所有活跃设备"""
        stmt = select(JiaDevice).where(JiaDevice.is_active.is_(True))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def register(
        self, db: AsyncSession, user_id: int, obj: DeviceRegisterParam
    ) -> JiaDevice:
        """注册设备（如果已存在则更新 FCM Token）"""
        # 按 user_id + device_id 查找
        existing = await self.get_by_user_and_device(db, user_id, obj.device_id)
        if existing:
            # 更新现有设备的 FCM Token
            existing.fcm_token = obj.fcm_token
            existing.device_name = obj.device_name or existing.device_name
            existing.device_type = obj.device_type or existing.device_type
            existing.is_active = True
            existing.last_active_time = timezone.now()
            await db.flush()
            return existing

        # 创建新设备
        device = JiaDevice(
            user_id=user_id,
            device_id=obj.device_id,
            fcm_token=obj.fcm_token,
            device_name=obj.device_name,
            device_type=obj.device_type,
        )
        db.add(device)
        await db.flush()
        return device

    async def update(
        self, db: AsyncSession, device_id: int, obj: DeviceUpdateParam
    ) -> JiaDevice | None:
        """更新设备信息"""
        device = await self.get_by_id(db, device_id)
        if not device:
            return None

        if obj.fcm_token is not None:
            device.fcm_token = obj.fcm_token
        if obj.device_name is not None:
            device.device_name = obj.device_name
        if obj.is_active is not None:
            device.is_active = obj.is_active

        device.last_active_time = timezone.now()
        await db.flush()
        return device

    async def deactivate(self, db: AsyncSession, fcm_token: str) -> bool:
        """停用设备（Token 失效时调用）"""
        stmt = (
            update(JiaDevice)
            .where(JiaDevice.fcm_token == fcm_token)
            .values(is_active=False)
        )
        result = await db.execute(stmt)
        return result.rowcount > 0

    async def delete(self, db: AsyncSession, device_id: int) -> bool:
        """删除设备"""
        device = await self.get_by_id(db, device_id)
        if device:
            await db.delete(device)
            return True
        return False


device_dao = CRUDDevice()
