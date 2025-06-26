#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from fastapi import Request
from sqlalchemy import func, select

from backend.common.exception import errors
from backend.common.security.jwt import superuser_verify
from backend.database.db import async_db_session
from backend.plugin.app_auth.crud import application_dao, authorization_dao, device_dao, redeem_code_dao
from backend.plugin.app_auth.model import AppAuthorization, AppApplication, AppDevice
from backend.plugin.app_auth.schema.authorization import (
    AuthorizationCheckResult,
    AuthorizeDeviceParam,
    CheckAuthorizationParam,
    CreateAuthorizationParam,
    RedeemCodeAuthParam,
    UpdateAuthorizationParam,
    UpdateAuthorizationTimeParam
)
from backend.plugin.app_auth.schema.redeem_code import RedeemCodeParam
from backend.plugin.app_auth.service.device_service import device_service
from backend.utils.timezone import timezone as tz


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
            
            # 检查应用是否存在
            app = await application_dao.get(db, obj.application_id)
            if not app:
                raise errors.NotFoundError(msg='应用不存在')
            
            # 检查设备是否存在
            device = await device_dao.get(db, obj.device_id)
            if not device:
                raise errors.NotFoundError(msg='设备不存在')
            
            # 检查是否已有有效授权
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
            
            # 检查应用是否存在
            app = await application_dao.get(db, obj.application_id)
            if not app:
                raise errors.NotFoundError(msg='应用不存在')
            
            # 获取或注册设备
            device = await device_service.register_or_update(obj.device_id)
            
            # 检查是否已有有效授权
            existing_auth = await authorization_dao.get_by_app_and_device(db, obj.application_id, device.id)
            if existing_auth:
                raise errors.ForbiddenError(msg='该设备已有有效授权')
            
            # 创建授权
            current_time = tz.now()
            end_time = current_time + timedelta(days=obj.duration_days)
            
            auth_data = CreateAuthorizationParam(
                application_id=obj.application_id,
                device_id=device.id,
                auth_type=1,  # 手动授权
                start_time=current_time,
                end_time=end_time,
                auth_source='手动授权',
                remark=obj.remark or f'手动授权 {obj.duration_days} 天'
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
            # 获取兑换码
            redeem_code = await redeem_code_dao.get_by_code(db, obj.code)
            if not redeem_code:
                raise errors.NotFoundError(msg='兑换码不存在')
            
            if redeem_code.is_used:
                raise errors.ForbiddenError(msg='兑换码已被使用')
            
            # 检查兑换码是否过期
            current_time = tz.now()
            if redeem_code.expire_time and redeem_code.expire_time < current_time:
                raise errors.ForbiddenError(msg='兑换码已过期')
            
            # 注册或更新设备
            device = await device_service.register_or_update(obj.device_id)
            
            # 检查是否已有有效授权
            existing_auth = await authorization_dao.get_by_app_and_device(
                db, redeem_code.application_id, device.id
            )
            if existing_auth:
                raise errors.ForbiddenError(msg='该设备已有有效授权')
            
            # 创建授权
            end_time = current_time + timedelta(days=redeem_code.duration_days)
            auth_data = CreateAuthorizationParam(
                application_id=redeem_code.application_id,
                device_id=device.id,
                auth_type=3,  # 兑换码授权
                start_time=current_time,
                end_time=end_time,
                auth_source=f'兑换码:{obj.code}',
                remark=f'通过兑换码 {obj.code} 获得 {redeem_code.duration_days} 天授权'
            )
            
            authorization = await authorization_dao.create(db, auth_data)
            
            # 标记兑换码为已使用
            await redeem_code_dao.use_code(db, redeem_code.id, obj.device_id)
            
            return authorization

    @staticmethod
    async def redeem_code_auth_legacy(obj: RedeemCodeParam) -> AppAuthorization:
        """
        兑换码授权

        :param obj: 兑换码参数
        :return:
        """
        async with async_db_session.begin() as db:
            # 获取兑换码
            redeem_code = await redeem_code_dao.get_by_code(db, obj.code)
            if not redeem_code:
                raise errors.NotFoundError(msg='兑换码不存在')
            
            if redeem_code.is_used:
                raise errors.ForbiddenError(msg='兑换码已被使用')
            
            # 检查兑换码是否过期
            current_time = tz.now()
            if redeem_code.expire_time and redeem_code.expire_time < current_time:
                raise errors.ForbiddenError(msg='兑换码已过期')
            
            # 注册或更新设备
            device = await device_service.register_or_update(obj.device_id)
            
            # 检查是否已有有效授权
            existing_auth = await authorization_dao.get_by_app_and_device(
                db, redeem_code.application_id, device.id
            )
            if existing_auth:
                raise errors.ForbiddenError(msg='该设备已有有效授权')
            
            # 创建授权
            end_time = current_time + timedelta(days=redeem_code.duration_days)
            auth_data = CreateAuthorizationParam(
                application_id=redeem_code.application_id,
                device_id=device.id,
                auth_type=3,  # 兑换码授权
                start_time=current_time,
                end_time=end_time,
                auth_source=f'兑换码:{obj.code}',
                remark=f'通过兑换码 {obj.code} 获得 {redeem_code.duration_days} 天授权'
            )
            
            authorization = await authorization_dao.create(db, auth_data)
            
            # 标记兑换码为已使用
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
            # 获取应用
            app = await application_dao.get_by_app_key(db, obj.app_key)
            if not app:
                return AuthorizationCheckResult(
                    is_authorized=False,
                    message='应用不存在'
                )
            
            # 如果应用是免费的，直接返回授权通过
            if app.is_free:
                # 注册或更新设备信息
                await device_service.register_or_update(obj.device_id)
                return AuthorizationCheckResult(
                    is_authorized=True,
                    status=1,
                    message='免费应用，授权通过'
                )
            
            # 获取或注册设备
            device = await device_service.register_or_update(obj.device_id)
            
            # 检查授权
            current_time = tz.now()
            authorization = await authorization_dao.check_authorization(
                db, app.id, device.id, current_time
            )
            
            if not authorization:
                return AuthorizationCheckResult(
                    is_authorized=False,
                    message='未找到有效授权'
                )
            
            # 计算剩余天数
            remaining_days = None
            if authorization.end_time:
                remaining_days = (authorization.end_time.date() - current_time.date()).days
                if remaining_days < 0:
                    remaining_days = 0
            
            return AuthorizationCheckResult(
                is_authorized=True,
                status=authorization.status,
                remaining_days=remaining_days,
                end_time=authorization.end_time,
                message='授权有效'
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
            # 检查应用是否存在
            app = await application_dao.get(db, application_id)
            if not app:
                raise errors.NotFoundError(msg='应用不存在')
            
            # 计算开始日期
            end_date = tz.now().date()
            start_date = end_date - timedelta(days=days - 1)
            
            # 查询每日注册数量
            stmt = select(
                func.date(AppAuthorization.created_time).label('date'),
                func.count(AppAuthorization.id).label('count')
            ).where(
                AppAuthorization.application_id == application_id,
                func.date(AppAuthorization.created_time) >= start_date,
                func.date(AppAuthorization.created_time) <= end_date
            ).group_by(
                func.date(AppAuthorization.created_time)
            ).order_by(
                func.date(AppAuthorization.created_time)
            )
            
            result = await db.execute(stmt)
            daily_data = {str(row.date): row.count for row in result.fetchall()}
            
            # 填充缺失的日期
            trend_data = []
            current_date = start_date
            while current_date <= end_date:
                date_str = str(current_date)
                trend_data.append({
                    'date': date_str,
                    'count': daily_data.get(date_str, 0)
                })
                current_date += timedelta(days=1)
            
            # 获取总统计
            total_stmt = select(func.count(AppAuthorization.id)).where(
                AppAuthorization.application_id == application_id
            )
            total_result = await db.execute(total_stmt)
            total_registrations = total_result.scalar()
            
            # 获取活跃设备数
            active_stmt = select(func.count(AppAuthorization.id)).where(
                AppAuthorization.application_id == application_id,
                AppAuthorization.status == 1
            )
            active_result = await db.execute(active_stmt)
            active_devices = active_result.scalar()
            
            return {
                'application_name': app.name,
                'total_registrations': total_registrations,
                'active_devices': active_devices,
                'trend_data': trend_data,
                'period': f'{start_date} 至 {end_date}'
            }

    @staticmethod
    async def get_device_authorization_history(device_id: int) -> dict:
        """
        获取设备授权历史

        :param device_id: 设备 ID
        :return:
        """
        async with async_db_session() as db:
            # 检查设备是否存在
            device = await device_dao.get(db, device_id)
            if not device:
                raise errors.NotFoundError(msg='设备不存在')
            
            # 查询设备的所有授权记录，包含应用信息
            stmt = select(
                AppAuthorization,
                AppApplication.name.label('application_name'),
                AppApplication.app_key.label('app_key')
            ).join(
                AppApplication, AppAuthorization.application_id == AppApplication.id
            ).where(
                AppAuthorization.device_id == device_id
            ).order_by(
                AppAuthorization.created_time.desc()
            )
            
            result = await db.execute(stmt)
            authorizations = []
            
            for row in result.fetchall():
                auth = row.AppAuthorization
                # 计算剩余天数
                remaining_days = None
                current_time = tz.now()
                if auth.end_time:
                    # 确保时区一致性
                    if auth.end_time.tzinfo is None:
                        # 如果 auth.end_time 没有时区信息，假设它是 UTC
                        auth_end_time = auth.end_time.replace(tzinfo=current_time.tzinfo)
                    else:
                        auth_end_time = auth.end_time
                    
                    remaining_days = (auth_end_time.date() - current_time.date()).days
                    if remaining_days < 0:
                        remaining_days = 0
                
                # 判断授权状态
                status_text = '未知'
                if auth.status == 0:
                    status_text = '已过期'
                elif auth.status == 1:
                    if auth.end_time:
                        # 确保时区一致性
                        if auth.end_time.tzinfo is None:
                            auth_end_time = auth.end_time.replace(tzinfo=current_time.tzinfo)
                        else:
                            auth_end_time = auth.end_time
                        
                        if auth_end_time < current_time:
                            status_text = '已过期'
                        else:
                            status_text = '正常'
                    else:
                        status_text = '正常'
                elif auth.status == 2:
                    status_text = '已禁用'
                
                # 授权类型
                auth_type_text = '未知'
                if auth.auth_type == 1:
                    auth_type_text = '手动授权'
                elif auth.auth_type == 2:
                    auth_type_text = '购买套餐'
                elif auth.auth_type == 3:
                    auth_type_text = '兑换码'
                
                authorizations.append({
                    'id': auth.id,
                    'application_name': row.application_name,
                    'app_key': row.app_key,
                    'auth_type': auth.auth_type,
                    'auth_type_text': auth_type_text,
                    'status': auth.status,
                    'status_text': status_text,
                    'start_time': auth.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'end_time': auth.end_time.strftime('%Y-%m-%d %H:%M:%S') if auth.end_time else '永久',
                    'remaining_days': remaining_days,
                    'auth_source': auth.auth_source,
                    'remark': auth.remark,
                    'created_time': auth.created_time.strftime('%Y-%m-%d %H:%M:%S')
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
                    'last_seen': device.last_seen.strftime('%Y-%m-%d %H:%M:%S') if device.last_seen else None
                },
                'authorizations': authorizations,
                'total_count': len(authorizations)
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
    async def get_list(application_id: int = None, device_id: int = None, 
                      status: int = None) -> list[AppAuthorization]:
        """获取授权列表"""
        async with async_db_session() as db:
            return await authorization_dao.get_list(
                db, application_id=application_id, device_id=device_id, status=status
            )

    @staticmethod
    def get_select(application_id: int = None, device_id: int = None, 
                  auth_type: int = None, status: int = None):
        """
        获取授权查询语句用于分页

        :param application_id: 应用 ID
        :param device_id: 设备 ID
        :param auth_type: 授权类型
        :param status: 状态
        :return:
        """
        return authorization_dao.get_select(
            application_id=application_id, device_id=device_id, 
            auth_type=auth_type, status=status
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
            # 检查授权是否存在
            auth = await authorization_dao.get(db, pk)
            if not auth:
                raise errors.NotFoundError(msg='授权不存在')
            
            # 构建更新参数
            update_data = UpdateAuthorizationParam(
                end_time=obj.end_time,
                remark=obj.remark
            )
            
            return await authorization_dao.update(db, pk, update_data)

    @staticmethod
    async def disable_authorization(pk: int) -> int:
        """
        使授权失效

        :param pk: 授权 ID
        :return:
        """
        async with async_db_session.begin() as db:
            # 检查授权是否存在
            auth = await authorization_dao.get(db, pk)
            if not auth:
                raise errors.NotFoundError(msg='授权不存在')
            
            # 设置状态为已禁用
            update_data = UpdateAuthorizationParam(
                status=2,  # 已禁用
                remark='手动失效'
            )
            
            return await authorization_dao.update(db, pk, update_data)


authorization_service = AuthorizationService()