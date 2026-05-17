#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import func, select

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
        """获取应用授权统计数据"""
        async with async_db_session() as db:
            applications_stmt = select(func.count(AppApplication.id)).where(AppApplication.status == 1)
            applications_result = await db.execute(applications_stmt)
            applications_count = applications_result.scalar() or 0

            devices_stmt = select(func.count(AppDevice.id)).where(AppDevice.status == 1)
            devices_result = await db.execute(devices_stmt)
            devices_count = devices_result.scalar() or 0

            current_time = timezone.now()
            authorizations_stmt = select(func.count(AppAuthorization.id)).where(
                AppAuthorization.status == 'active',
                (AppAuthorization.valid_to.is_(None)) | (AppAuthorization.valid_to > current_time)
            )
            authorizations_result = await db.execute(authorizations_stmt)
            authorizations_count = authorizations_result.scalar() or 0

            redeem_codes_stmt = select(func.count(AppRedeemCode.id))
            redeem_codes_result = await db.execute(redeem_codes_stmt)
            redeem_codes_count = redeem_codes_result.scalar() or 0

            active_authorizations_stmt = select(func.count(AppAuthorization.id)).where(
                AppAuthorization.status == 'active'
            )
            active_authorizations_result = await db.execute(active_authorizations_stmt)
            active_authorizations_count = active_authorizations_result.scalar() or 0

            expired_authorizations_stmt = select(func.count(AppAuthorization.id)).where(
                AppAuthorization.valid_to.is_not(None),
                AppAuthorization.valid_to <= current_time
            )
            expired_authorizations_result = await db.execute(expired_authorizations_stmt)
            expired_authorizations_count = expired_authorizations_result.scalar() or 0

            orders_stmt = select(func.count(AppOrder.id))
            orders_result = await db.execute(orders_stmt)
            orders_count = orders_result.scalar() or 0

            packages_stmt = select(func.count(AppPackage.id)).where(AppPackage.status == 'active')
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
