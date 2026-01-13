#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import UserDevice
from backend.utils.timezone import timezone


class CRUDUserDevice(CRUDPlus[UserDevice]):
    """用户设备数据库操作类"""

    async def get_by_device_id(self, db: AsyncSession, device_id: str) -> UserDevice | None:
        """
        通过设备 ID 获取设备记录

        :param db: 数据库会话
        :param device_id: 设备唯一标识
        :return:
        """
        return await self.select_model_by_column(db, device_id=device_id)

    async def create_or_update_device(
        self,
        db: AsyncSession,
        user_id: int,
        device_id: str,
        platform: str,
        device_model: str | None = None,
        os_version: str | None = None,
        app_version: str | None = None,
        push_token: str | None = None,
        last_ip: str | None = None,
        last_city: str | None = None,
    ) -> UserDevice:
        """
        创建或更新设备记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param device_id: 设备唯一标识
        :param platform: 平台
        :param device_model: 设备型号
        :param os_version: 操作系统版本
        :param app_version: App 版本
        :param push_token: 推送 Token
        :param last_ip: 最近 IP
        :param last_city: 最近城市
        :return:
        """
        device = await self.get_by_device_id(db, device_id)

        now = timezone.now()

        if device:
            # 更新现有设备记录
            update_data = {
                'platform': platform,
                'last_login_time': now,
                'is_online': True,
            }

            if device_model:
                update_data['device_model'] = device_model
            if os_version:
                update_data['os_version'] = os_version
            if app_version:
                update_data['app_version'] = app_version
            if push_token:
                update_data['push_token'] = push_token
            if last_ip:
                update_data['last_ip'] = last_ip
            if last_city:
                update_data['last_city'] = last_city

            await self.update_model(db, device.id, update_data)
            await db.refresh(device)
            return device
        else:
            # 创建新设备记录
            device_data = UserDevice(
                user_id=user_id,
                device_id=device_id,
                platform=platform,
                device_model=device_model,
                os_version=os_version,
                app_version=app_version,
                push_token=push_token,
                last_login_time=now,
                last_ip=last_ip,
                last_city=last_city,
                is_online=True,
            )

            db.add(device_data)
            await db.flush()
            return device_data

    async def set_offline(self, db: AsyncSession, device_id: str) -> int:
        """
        设置设备为离线状态

        :param db: 数据库会话
        :param device_id: 设备唯一标识
        :return:
        """
        device = await self.get_by_device_id(db, device_id)
        if not device:
            return 0

        return await self.update_model(db, device.id, {'is_online': False})

    async def update_push_token(self, db: AsyncSession, device_id: str, push_token: str) -> int:
        """
        更新推送 Token

        :param db: 数据库会话
        :param device_id: 设备唯一标识
        :param push_token: 推送 Token
        :return:
        """
        device = await self.get_by_device_id(db, device_id)
        if not device:
            return 0

        return await self.update_model(db, device.id, {'push_token': push_token})


user_device_dao: CRUDUserDevice = CRUDUserDevice(UserDevice)
