#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.crud import device_dao
from backend.app.jia.schema import PushResult
from backend.common.log import log
from backend.core.conf import settings


class PushService:
    """FCM 推送服务"""

    _initialized: bool = False

    @classmethod
    def initialize(cls) -> None:
        """初始化 Firebase Admin SDK"""
        if cls._initialized:
            return

        try:
            # Firebase 凭证文件路径（在 settings 中配置）
            cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
            if not cred_path:
                log.warning('FIREBASE_CREDENTIALS_PATH 未配置，推送服务不可用')
                return

            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            cls._initialized = True
            log.info('Firebase Admin SDK 初始化成功')
        except Exception as e:
            log.error(f'Firebase Admin SDK 初始化失败: {e}')

    @classmethod
    def is_available(cls) -> bool:
        """检查推送服务是否可用"""
        return cls._initialized

    async def send_to_token(
        self,
        token: str,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> PushResult:
        """
        发送推送到指定设备

        :param token: FCM Token
        :param title: 通知标题
        :param body: 通知内容
        :param data: 额外数据
        :return: 推送结果
        """
        if not self.is_available():
            return PushResult(success=False, error='推送服务不可用')

        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=token,
            )

            response = messaging.send(message)
            log.info(f'推送成功: {response}')
            return PushResult(success=True, message_id=response)

        except messaging.UnregisteredError:
            log.warning(f'Token 已失效: {token[:20]}...')
            return PushResult(success=False, error='设备 Token 已失效')

        except Exception as e:
            log.error(f'推送失败: {e}')
            return PushResult(success=False, error=str(e))

    async def send_to_user(
        self,
        db: AsyncSession,
        user_id: int,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> list[PushResult]:
        """
        发送推送给指定用户的所有设备

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param title: 通知标题
        :param body: 通知内容
        :param data: 额外数据
        :return: 推送结果列表
        """
        devices = await device_dao.get_by_user_id(db, user_id)
        if not devices:
            return [PushResult(success=False, error='用户没有注册设备')]

        results = []
        for device in devices:
            result = await self.send_to_token(device.fcm_token, title, body, data)
            results.append(result)

            # 如果 Token 失效，停用设备
            if not result.success and 'Token 已失效' in (result.error or ''):
                await device_dao.deactivate(db, device.fcm_token)

        return results

    async def send_to_all(
        self,
        db: AsyncSession,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> list[PushResult]:
        """
        发送推送给所有活跃设备

        :param db: 数据库会话
        :param title: 通知标题
        :param body: 通知内容
        :param data: 额外数据
        :return: 推送结果列表
        """
        devices = await device_dao.get_all_active(db)
        if not devices:
            return [PushResult(success=False, error='没有活跃设备')]

        results = []
        for device in devices:
            result = await self.send_to_token(device.fcm_token, title, body, data)
            results.append(result)

            # 如果 Token 失效，停用设备
            if not result.success and 'Token 已失效' in (result.error or ''):
                await device_dao.deactivate(db, device.fcm_token)

        return results


push_service = PushService()
