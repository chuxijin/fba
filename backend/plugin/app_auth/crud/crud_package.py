#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.app_auth.model import AppPackage, AppApplication
from backend.plugin.app_auth.schema.package import CreatePackageParam, UpdatePackageParam


class CRUDPackage(CRUDPlus[AppPackage]):
    """套餐数据库操作类"""

    async def get(self, db: AsyncSession, package_id: int) -> AppPackage | None:
        """
        获取套餐详情

        :param db: 数据库会话
        :param package_id: 套餐 ID
        :return:
        """
        return await self.select_model(db, package_id)

    async def create(self, db: AsyncSession, obj_in: CreatePackageParam) -> AppPackage:
        """
        创建套餐

        :param db: 数据库会话
        :param obj_in: 创建参数
        :return:
        """
        return await self.create_model(db, obj_in)

    async def update(self, db: AsyncSession, package_id: int, obj_in: UpdatePackageParam) -> int:
        """
        更新套餐

        :param db: 数据库会话
        :param package_id: 套餐 ID
        :param obj_in: 更新参数
        :return:
        """
        return await self.update_model(db, package_id, obj_in)

    async def delete(self, db: AsyncSession, package_id: int) -> int:
        """删除套餐"""
        return await self.delete_model(db, package_id)

    async def get_by_application(self, db: AsyncSession, application_id: int) -> list[AppPackage]:
        """
        获取应用的套餐列表

        :param db: 数据库会话
        :param application_id: 应用 ID
        :return:
        """
        stmt = select(self.model).where(
            self.model.application_id == application_id,
            self.model.is_active == True
        ).order_by(self.model.created_time.desc())
        return await self.select_models(db, stmt)

    async def get_list(self, db: AsyncSession, application_id: int = None, is_active: bool = None) -> list[AppPackage]:
        """获取套餐列表"""
        stmt = select(self.model)
        if application_id:
            stmt = stmt.where(self.model.application_id == application_id)
        if is_active is not None:
            stmt = stmt.where(self.model.is_active == is_active)
        stmt = stmt.order_by(self.model.created_time.desc())
        return await self.select_models(db, stmt)

    def get_select(self, application_id: int = None, name: str = None, is_active: bool = None):
        """获取套餐查询语句，包含应用信息"""
        stmt = select(
            self.model,
            AppApplication.name.label('application_name')
        ).join(
            AppApplication, self.model.application_id == AppApplication.id
        )
        if application_id:
            stmt = stmt.where(self.model.application_id == application_id)
        if name:
            stmt = stmt.where(self.model.name.like(f'%{name}%'))
        if is_active is not None:
            stmt = stmt.where(self.model.is_active == is_active)
        stmt = stmt.order_by(self.model.created_time.desc())
        return stmt


package_dao: CRUDPackage = CRUDPackage(AppPackage)