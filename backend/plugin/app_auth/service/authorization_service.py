#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import timedelta

from fastapi import Request
from sqlalchemy import func, select

from backend.common.exception import errors
from backend.common.security.jwt import superuser_verify
from backend.database.db import async_db_session
from backend.plugin.app_auth.crud import application_dao, authorization_dao, device_dao, redeem_code_dao
from backend.plugin.app_auth.model import AppApplication, AppAuthorization
from backend.plugin.app_auth.schema.authorization import (
    AuthorizationCheckResult,
    AuthorizeDeviceParam,
    CheckAuthorizationParam,
    CreateAuthorizationParam,
    RedeemCodeAuthParam,
    UpdateAuthorizationParam,
    UpdateAuthorizationTimeParam,
)
from backend.plugin.app_auth.schema.redeem_code import RedeemCodeParam
from backend.plugin.app_auth.service.device_service import device_service
from backend.utils.timezone import timezone as tz


SOURCE_LABEL = {
    'manual': '手动授权',
    'purchase': '购买套餐',
    'redeem_code': '兑换码',
}

STATUS_LABEL = {
    'active': '正常',
    'expired': '已过期',
    'paused': '已禁用',
}


class AuthorizationService:
    """授权服务类"""

    @staticmethod
    async def create_manual_auth(*, request: Request, obj: CreateAuthorizationParam) -> AppAuthorization:
        """
        创建手动授权

        :param request: FastAPI 请求对象
        :param obj: 创建参数
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)

            app = await application_dao.get(db, obj.application_id)
            if not app:
                raise errors.NotFoundError(msg='应用不存在')

            device = await device_dao.get(db, obj.device_id)
            if not device:
                raise errors.NotFoundError(msg='设备不存在')

            existing_auth = await authorization_dao.get_by_app_and_device(db, obj.application_id, obj.device_id)
            if existing_auth:
                raise errors.ForbiddenError(msg='该设备已有有效授权')

            return await authorization_dao.create(db, obj)

    @staticmethod
    async def manual_authorize(*, request: Request, obj: AuthorizeDeviceParam) -> AppAuthorization:
        """
        手动授权设备

        :param request: FastAPI 请求对象
        :param obj: 授权参数
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)

            app = await application_dao.get(db, obj.application_id)
            if not app:
                raise errors.NotFoundError(msg='应用不存在')

            device = await device_service.register_or_update(obj.device_id)

            existing_auth = await authorization_dao.get_by_app_and_device(db, obj.application_id, device.id)
            if existing_auth:
                raise errors.ForbiddenError(msg='该设备已有有效授权')

            current_time = tz.now()
            valid_to = current_time + timedelta(days=obj.duration_days)

            auth_data = CreateAuthorizationParam(
                application_id=obj.application_id,
                device_id=device.id,
                source='manual',
                valid_from=current_time,
                valid_to=valid_to,
                source_ref='manual_grant',
                template_code=obj.template_code,
                remark=obj.remark or f'手动授权 {obj.duration_days} 天',
            )

            return await authorization_dao.create(db, auth_data)

    @staticmethod
    async def redeem_code_auth(obj: RedeemCodeAuthParam) -> AppAuthorization:
        """
        兑换码授权（新版本）

        :param obj: 兑换码授权参数
        :return:
        """
        async with async_db_session.begin() as db:
            redeem_code = await redeem_code_dao.get_by_code(db, obj.code)
            if not redeem_code:
                raise errors.NotFoundError(msg='兑换码不存在')

            if redeem_code.is_used:
                raise errors.ForbiddenError(msg='兑换码已被使用')

            current_time = tz.now()
            if redeem_code.expire_time and redeem_code.expire_time < current_time:
                raise errors.ForbiddenError(msg='兑换码已过期')

            device = await device_service.register_or_update(obj.device_id)

            existing_auth = await authorization_dao.get_by_app_and_device(db, redeem_code.application_id, device.id)
            if existing_auth:
                raise errors.ForbiddenError(msg='该设备已有有效授权')

            valid_to = current_time + timedelta(days=redeem_code.duration_days)
            auth_data = CreateAuthorizationParam(
                application_id=redeem_code.application_id,
                device_id=device.id,
                source='redeem_code',
                valid_from=current_time,
                valid_to=valid_to,
                source_ref=f'redeem_code:{obj.code}',
                template_code=None,
                remark=f'通过兑换码 {obj.code} 获得 {redeem_code.duration_days} 天授权',
            )

            authorization = await authorization_dao.create(db, auth_data)

            await redeem_code_dao.use_code(db, redeem_code.id, obj.device_id)

            return authorization

    @staticmethod
    async def redeem_code_auth_legacy(obj: RedeemCodeParam) -> AppAuthorization:
        """
        兑换码授权(兼容旧入口)

        :param obj: 兑换码参数
        :return:
        """
        async with async_db_session.begin() as db:
            redeem_code = await redeem_code_dao.get_by_code(db, obj.code)
            if not redeem_code:
                raise errors.NotFoundError(msg='兑换码不存在')

            if redeem_code.is_used:
                raise errors.ForbiddenError(msg='兑换码已被使用')

            current_time = tz.now()
            if redeem_code.expire_time and redeem_code.expire_time < current_time:
                raise errors.ForbiddenError(msg='兑换码已过期')

            device = await device_service.register_or_update(obj.device_id)

            existing_auth = await authorization_dao.get_by_app_and_device(db, redeem_code.application_id, device.id)
            if existing_auth:
                raise errors.ForbiddenError(msg='该设备已有有效授权')

            valid_to = current_time + timedelta(days=redeem_code.duration_days)
            auth_data = CreateAuthorizationParam(
                application_id=redeem_code.application_id,
                device_id=device.id,
                source='redeem_code',
                valid_from=current_time,
                valid_to=valid_to,
                source_ref=f'redeem_code:{obj.code}',
                template_code=None,
                remark=f'通过兑换码 {obj.code} 获得 {redeem_code.duration_days} 天授权',
            )

            authorization = await authorization_dao.create(db, auth_data)

            await redeem_code_dao.use_code(db, redeem_code.id, obj.used_by or obj.device_id)

            return authorization

    @staticmethod
    async def check_authorization(obj: CheckAuthorizationParam) -> AuthorizationCheckResult:
        """
        检查授权

        :param obj: 检查参数
        :return:
        """
        async with async_db_session() as db:
            app = await application_dao.get_by_app_key(db, obj.app_key)
            if not app:
                return AuthorizationCheckResult(
                    is_authorized=False, status=None, remaining_days=None, valid_to=None, message='应用不存在'
                )

            if app.is_free:
                await device_service.register_or_update(obj.device_id)
                return AuthorizationCheckResult(
                    is_authorized=True,
                    status='active',
                    remaining_days=None,
                    valid_to=None,
                    message='免费应用，授权通过',
                )

            device = await device_service.register_or_update(obj.device_id)

            current_time = tz.now()
            authorization = await authorization_dao.check_authorization(db, app.id, device.id, current_time)

            if not authorization:
                return AuthorizationCheckResult(
                    is_authorized=False, status=None, remaining_days=None, valid_to=None, message='未找到有效授权'
                )

            remaining_days = None
            if authorization.valid_to:
                remaining_days = (authorization.valid_to.date() - current_time.date()).days
                if remaining_days < 0:
                    remaining_days = 0

            return AuthorizationCheckResult(
                is_authorized=True,
                status=authorization.status,
                remaining_days=remaining_days,
                valid_to=authorization.valid_to,
                message='授权有效',
            )

    @staticmethod
    async def get_application_registration_trend(application_id: int, days: int = 30) -> dict:
        """
        获取应用注册趋势数据

        :param application_id: 应用 ID
        :param days: 统计天数
        :return:
        """
        async with async_db_session() as db:
            app = await application_dao.get(db, application_id)
            if not app:
                raise errors.NotFoundError(msg='应用不存在')

            end_date = tz.now().date()
            start_date = end_date - timedelta(days=days - 1)

            stmt = (
                select(
                    func.date(AppAuthorization.created_time).label('date'),
                    func.count(AppAuthorization.id).label('count'),
                )
                .where(
                    AppAuthorization.application_id == application_id,
                    func.date(AppAuthorization.created_time) >= start_date,
                    func.date(AppAuthorization.created_time) <= end_date,
                )
                .group_by(func.date(AppAuthorization.created_time))
                .order_by(func.date(AppAuthorization.created_time))
            )

            result = await db.execute(stmt)
            daily_data = {str(row.date): row.count for row in result.fetchall()}

            trend_data = []
            current_date = start_date
            while current_date <= end_date:
                date_str = str(current_date)
                trend_data.append({'date': date_str, 'count': daily_data.get(date_str, 0)})
                current_date += timedelta(days=1)

            total_stmt = select(func.count(AppAuthorization.id)).where(
                AppAuthorization.application_id == application_id
            )
            total_result = await db.execute(total_stmt)
            total_registrations = total_result.scalar()

            active_stmt = select(func.count(AppAuthorization.id)).where(
                AppAuthorization.application_id == application_id, AppAuthorization.status == 'active'
            )
            active_result = await db.execute(active_stmt)
            active_devices = active_result.scalar()

            return {
                'application_name': app.name,
                'total_registrations': total_registrations,
                'active_devices': active_devices,
                'trend_data': trend_data,
                'period': f'{start_date} 至 {end_date}',
            }

    @staticmethod
    async def get_device_authorization_history(device_id: int) -> dict:
        """
        获取设备授权历史

        :param device_id: 设备 ID
        :return:
        """
        async with async_db_session() as db:
            device = await device_dao.get(db, device_id)
            if not device:
                raise errors.NotFoundError(msg='设备不存在')

            stmt = (
                select(
                    AppAuthorization,
                    AppApplication.name.label('application_name'),
                    AppApplication.app_key.label('app_key'),
                )
                .join(AppApplication, AppAuthorization.application_id == AppApplication.id)
                .where(AppAuthorization.device_id == device_id)
                .order_by(AppAuthorization.created_time.desc())
            )

            result = await db.execute(stmt)
            authorizations = []

            for row in result.fetchall():
                auth = row.AppAuthorization
                remaining_days = None
                current_time = tz.now()
                if auth.valid_to:
                    if auth.valid_to.tzinfo is None:
                        auth_valid_to = auth.valid_to.replace(tzinfo=current_time.tzinfo)
                    else:
                        auth_valid_to = auth.valid_to

                    remaining_days = (auth_valid_to.date() - current_time.date()).days
                    if remaining_days < 0:
                        remaining_days = 0

                # 计算实时状态文本(考虑过期)
                status_text = STATUS_LABEL.get(auth.status, auth.status)
                if auth.status == 'active' and auth.valid_to:
                    if auth.valid_to.tzinfo is None:
                        auth_valid_to = auth.valid_to.replace(tzinfo=current_time.tzinfo)
                    else:
                        auth_valid_to = auth.valid_to
                    if auth_valid_to < current_time:
                        status_text = STATUS_LABEL['expired']

                source_text = SOURCE_LABEL.get(auth.source, auth.source)

                authorizations.append({
                    'id': auth.id,
                    'application_name': row.application_name,
                    'app_key': row.app_key,
                    'source': auth.source,
                    'source_text': source_text,
                    'status': auth.status,
                    'status_text': status_text,
                    'valid_from': auth.valid_from.strftime('%Y-%m-%d %H:%M:%S'),
                    'valid_to': auth.valid_to.strftime('%Y-%m-%d %H:%M:%S') if auth.valid_to else '永久',
                    'remaining_days': remaining_days,
                    'source_ref': auth.source_ref,
                    'template_code': auth.template_code,
                    'remark': auth.remark,
                    'created_time': auth.created_time.strftime('%Y-%m-%d %H:%M:%S'),
                })

            return {
                'device_info': {
                    'id': device.id,
                    'device_id': device.device_id,
                    'device_name': device.device_name,
                    'device_type': device.device_type,
                    'os_info': device.os_info,
                    'ip_address': device.ip_address,
                    'status': device.status,
                    'first_seen': device.first_seen.strftime('%Y-%m-%d %H:%M:%S'),
                    'last_seen': device.last_seen.strftime('%Y-%m-%d %H:%M:%S') if device.last_seen else None,
                },
                'authorizations': authorizations,
                'total_count': len(authorizations),
            }

    @staticmethod
    async def update(*, request: Request, auth_id: int, obj: UpdateAuthorizationParam) -> int:
        """
        更新授权

        :param request: FastAPI 请求对象
        :param auth_id: 授权 ID
        :param obj: 更新参数
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)

            auth = await authorization_dao.get(db, auth_id)
            if not auth:
                raise errors.NotFoundError(msg='授权不存在')

            return await authorization_dao.update(db, auth_id, obj)

    @staticmethod
    async def delete(*, request: Request, auth_id: int) -> int:
        """
        删除授权

        :param request: FastAPI 请求对象
        :param auth_id: 授权 ID
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)

            auth = await authorization_dao.get(db, auth_id)
            if not auth:
                raise errors.NotFoundError(msg='授权不存在')

            return await authorization_dao.delete(db, auth_id)

    @staticmethod
    async def get(auth_id: int) -> AppAuthorization:
        """
        获取授权详情

        :param auth_id: 授权 ID
        :return:
        """
        async with async_db_session() as db:
            auth = await authorization_dao.get(db, auth_id)
            if not auth:
                raise errors.NotFoundError(msg='授权不存在')
            return auth

    @staticmethod
    async def get_list(application_id: int = None, device_id: int = None, status: str = None) -> list[AppAuthorization]:
        """获取授权列表"""
        async with async_db_session() as db:
            return await authorization_dao.get_list(
                db, application_id=application_id, device_id=device_id, status=status
            )

    @staticmethod
    def get_select(application_id: int = None, device_id: int = None, source: str = None, status: str = None):
        """
        获取授权查询语句用于分页

        :param application_id: 应用 ID
        :param device_id: 设备 ID
        :param source: 授权来源
        :param status: 状态
        :return:
        """
        return authorization_dao.get_select(
            application_id=application_id, device_id=device_id, source=source, status=status
        )

    @staticmethod
    async def update_authorization_time(pk: int, obj: UpdateAuthorizationTimeParam) -> int:
        """
        修改授权时间

        :param pk: 授权 ID
        :param obj: 修改参数
        :return:
        """
        async with async_db_session.begin() as db:
            auth = await authorization_dao.get(db, pk)
            if not auth:
                raise errors.NotFoundError(msg='授权不存在')

            update_data = UpdateAuthorizationParam(valid_to=obj.valid_to, remark=obj.remark)

            return await authorization_dao.update(db, pk, update_data)

    @staticmethod
    async def disable_authorization(pk: int) -> int:
        """
        使授权失效

        :param pk: 授权 ID
        :return:
        """
        async with async_db_session.begin() as db:
            auth = await authorization_dao.get(db, pk)
            if not auth:
                raise errors.NotFoundError(msg='授权不存在')

            update_data = UpdateAuthorizationParam(status='paused', remark='手动失效')

            return await authorization_dao.update(db, pk, update_data)


authorization_service = AuthorizationService()
