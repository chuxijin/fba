#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import async_db_session
from backend.plugin.app_auth.model.application import AppApplication
from backend.plugin.app_auth.model.authorization import AppAuthorization
from backend.plugin.app_auth.model.device import AppDevice
from backend.plugin.app_auth.model.order import AppOrder
from backend.plugin.app_auth.model.package import AppPackage
from backend.plugin.app_auth.model.redeem_code import AppRedeemCode
from backend.plugin.app_auth.schema.statistics import AppAuthStatistics
from backend.utils.timezone import timezone


class StatisticsService:
    """统计数据服务"""

    @staticmethod
    async def get_app_auth_statistics() -> AppAuthStatistics:
        """
        获取应用授权统计数据
        
        :return: 统计数据
        """
        async with async_db_session() as db:
            # 应用总数
            applications_stmt = select(func.count(AppApplication.id)).where(AppApplication.status == 1)
            applications_result = await db.execute(applications_stmt)
            applications_count = applications_result.scalar() or 0

            # 设备总数
            devices_stmt = select(func.count(AppDevice.id)).where(AppDevice.status == 1)
            devices_result = await db.execute(devices_stmt)
            devices_count = devices_result.scalar() or 0

            # 有效授权数（状态为1且未过期）
            current_time = timezone.now()
            authorizations_stmt = select(func.count(AppAuthorization.id)).where(
                AppAuthorization.status == 1,
                (AppAuthorization.end_time.is_(None)) | (AppAuthorization.end_time > current_time)
            )
            authorizations_result = await db.execute(authorizations_stmt)
            authorizations_count = authorizations_result.scalar() or 0

            # 兑换码总数
            redeem_codes_stmt = select(func.count(AppRedeemCode.id))
            redeem_codes_result = await db.execute(redeem_codes_stmt)
            redeem_codes_count = redeem_codes_result.scalar() or 0

            # 活跃授权数（状态为1）
            active_authorizations_stmt = select(func.count(AppAuthorization.id)).where(
                AppAuthorization.status == 1
            )
            active_authorizations_result = await db.execute(active_authorizations_stmt)
            active_authorizations_count = active_authorizations_result.scalar() or 0

            # 过期授权数
            expired_authorizations_stmt = select(func.count(AppAuthorization.id)).where(
                AppAuthorization.end_time.is_not(None),
                AppAuthorization.end_time <= current_time
            )
            expired_authorizations_result = await db.execute(expired_authorizations_stmt)
            expired_authorizations_count = expired_authorizations_result.scalar() or 0

            # 订单总数
            orders_stmt = select(func.count(AppOrder.id))
            orders_result = await db.execute(orders_stmt)
            orders_count = orders_result.scalar() or 0

            # 套餐总数
            packages_stmt = select(func.count(AppPackage.id)).where(AppPackage.is_active == True)
            packages_result = await db.execute(packages_stmt)
            packages_count = packages_result.scalar() or 0

            return AppAuthStatistics(
                applications=applications_count,
                devices=devices_count,
                authorizations=authorizations_count,
                redeem_codes=redeem_codes_count,
                active_authorizations=active_authorizations_count,
                expired_authorizations=expired_authorizations_count,
                total_orders=orders_count,
                total_packages=packages_count
            ) 