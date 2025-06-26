#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from decimal import Decimal

from fastapi import Request

from backend.common.exception import errors
from backend.common.security.jwt import superuser_verify
from backend.database.db import async_db_session
from backend.plugin.app_auth.crud import application_dao, package_dao
from backend.plugin.app_auth.model import AppPackage
from backend.plugin.app_auth.schema.package import CreatePackageParam, UpdatePackageParam


class PackageService:
    """套餐服务类"""

    @staticmethod
    async def create(*, request: Request, obj: CreatePackageParam) -> AppPackage:
        """
        创建套餐

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
            
            return await package_dao.create(db, obj)

    @staticmethod
    async def update(*, request: Request, package_id: int, obj: UpdatePackageParam) -> int:
        """
        更新套餐

        :param request: FastAPI 请求对象
        :param package_id: 套餐 ID
        :param obj: 更新参数
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)
            
            package = await package_dao.get(db, package_id)
            if not package:
                raise errors.NotFoundError(msg='套餐不存在')
            
            return await package_dao.update(db, package_id, obj)

    @staticmethod
    async def delete(*, request: Request, package_id: int) -> int:
        """
        删除套餐

        :param request: FastAPI 请求对象
        :param package_id: 套餐 ID
        :return:
        """
        async with async_db_session.begin() as db:
            superuser_verify(request)
            
            package = await package_dao.get(db, package_id)
            if not package:
                raise errors.NotFoundError(msg='套餐不存在')
            
            return await package_dao.delete(db, package_id)

    @staticmethod
    async def get(package_id: int) -> AppPackage:
        """
        获取套餐详情

        :param package_id: 套餐 ID
        :return:
        """
        async with async_db_session() as db:
            package = await package_dao.get(db, package_id)
            if not package:
                raise errors.NotFoundError(msg='套餐不存在')
            return package

    @staticmethod
    async def get_list(application_id: int = None, is_active: bool = None) -> list[AppPackage]:
        """获取套餐列表"""
        async with async_db_session() as db:
            return await package_dao.get_list(db, application_id=application_id, is_active=is_active)

    @staticmethod
    def get_select(application_id: int = None, name: str = None, is_active: bool = None):
        """获取套餐查询语句用于分页"""
        return package_dao.get_select(application_id=application_id, name=name, is_active=is_active)

    @staticmethod
    async def get_pagination_list(db, application_id: int = None, name: str = None, is_active: bool = None):
        """获取套餐分页列表，包含应用信息"""
        from backend.plugin.app_auth.model import AppApplication
        from sqlalchemy import select
        from backend.utils.timezone import timezone
        
        stmt = select(
            package_dao.model,
            AppApplication.name.label('application_name')
        ).join(
            AppApplication, package_dao.model.application_id == AppApplication.id
        )
        
        if application_id:
            stmt = stmt.where(package_dao.model.application_id == application_id)
        if name:
            stmt = stmt.where(package_dao.model.name.like(f'%{name}%'))
        if is_active is not None:
            stmt = stmt.where(package_dao.model.is_active == is_active)
        stmt = stmt.order_by(package_dao.model.created_time.desc())
        
        result = await db.execute(stmt)
        packages = []
        
        for row in result.fetchall():
            package = row[0]  # AppPackage 对象
            application_name = row[1]  # 应用名称
            
            # 计算当前价格
            current_price = package.original_price
            if package.discount_rate:
                current_time = timezone.now()
                if (not package.discount_start_time or current_time >= package.discount_start_time) and \
                   (not package.discount_end_time or current_time <= package.discount_end_time):
                    current_price = package.original_price * package.discount_rate
            
            package_dict = {
                'id': package.id,
                'application_id': package.application_id,
                'application_name': application_name,
                'name': package.name,
                'description': package.description,
                'duration_days': package.duration_days,
                'original_price': str(package.original_price),
                'current_price': str(current_price),
                'discount_rate': str(package.discount_rate) if package.discount_rate else None,
                'discount_start_time': package.discount_start_time.isoformat() if package.discount_start_time else None,
                'discount_end_time': package.discount_end_time.isoformat() if package.discount_end_time else None,
                'max_devices': package.max_devices,
                'is_active': package.is_active,
                'sort_order': package.sort_order,
                'created_time': package.created_time.isoformat(),
                'updated_time': package.updated_time.isoformat() if package.updated_time else None,
            }
            packages.append(package_dict)
        
        return packages

    @staticmethod
    async def get_options(application_id: int = None) -> list[dict]:
        """获取套餐选择选项"""
        async with async_db_session() as db:
            packages = await package_dao.get_list(db, application_id=application_id, is_active=True)  # 只获取启用的套餐
            return [
                {
                    'label': f"{package.name} - {package.current_price}元/{package.duration_days}天",
                    'value': package.id
                }
                for package in packages
            ]

    @staticmethod
    async def get_options_by_application(application_id: int) -> list[dict]:
        """根据应用获取套餐选项"""
        return await PackageService.get_options(application_id=application_id)

    @staticmethod
    def calculate_current_price(package: AppPackage) -> Decimal:
        """
        计算套餐当前价格

        :param package: 套餐对象
        :return: 当前价格
        """
        from backend.utils.timezone import timezone
        
        # 如果没有折扣率，返回原价
        if not package.discount_rate:
            return package.original_price
        
        # 检查折扣时间
        current_time = timezone.now()
        if package.discount_start_time and current_time < package.discount_start_time:
            return package.original_price
        if package.discount_end_time and current_time > package.discount_end_time:
            return package.original_price
        
        # 计算折扣价
        return package.original_price * package.discount_rate


package_service = PackageService()