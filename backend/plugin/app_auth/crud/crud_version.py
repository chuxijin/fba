#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.app_auth.model import AppVersion
from backend.plugin.app_auth.schema.version import CreateVersionParam, UpdateVersionParam


class CRUDVersion(CRUDPlus[AppVersion]):
    """版本数据库操作类"""

    async def get(self, db: AsyncSession, version_id: int) -> AppVersion | None:
        """
        获取版本详情

        :param db: 数据库会话
        :param version_id: 版本 ID
        :return:
        """
        return await self.select_model(db, version_id)

    async def create(self, db: AsyncSession, obj_in: CreateVersionParam) -> AppVersion:
        """
        创建版本

        :param db: 数据库会话
        :param obj_in: 创建参数
        :return:
        """
        return await self.create_model(db, obj_in)

    async def update(self, db: AsyncSession, version_id: int, obj_in: UpdateVersionParam) -> int:
        """
        更新版本

        :param db: 数据库会话
        :param version_id: 版本 ID
        :param obj_in: 更新参数
        :return:
        """
        return await self.update_model(db, version_id, obj_in)

    async def delete(self, db: AsyncSession, version_id: int) -> int:
        """删除版本"""
        return await self.delete_model(db, version_id)

    async def get_by_application(self, db: AsyncSession, application_id: int) -> list[AppVersion]:
        """
        获取应用的版本列表

        :param db: 数据库会话
        :param application_id: 应用 ID
        :return:
        """
        stmt = select(self.model).where(
            self.model.application_id == application_id,
            self.model.is_active == True
        ).order_by(self.model.created_time.desc())
        return await self.select_models(db, stmt)

    async def get_latest_version(self, db: AsyncSession, application_id: int) -> AppVersion | None:
        """
        获取应用最新版本

        :param db: 数据库会话
        :param application_id: 应用 ID
        :return:
        """
        stmt = select(self.model).where(
            self.model.application_id == application_id,
            self.model.is_latest == True,
            self.model.is_active == True
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def set_latest_version(self, db: AsyncSession, application_id: int, version_id: int) -> None:
        """
        设置最新版本

        :param db: 数据库会话
        :param application_id: 应用 ID
        :param version_id: 版本 ID
        :return:
        """
        # 先将该应用的所有版本设为非最新
        await self.update_models_by_column(db, {'is_latest': False}, application_id=application_id)
        # 再将指定版本设为最新
        await self.update_model(db, version_id, {'is_latest': True})

    async def get_list(self, db: AsyncSession, application_id: int = None, version_name: str = None, is_active: bool = None) -> list[AppVersion]:
        """获取版本列表"""
        stmt = select(self.model)
        if application_id:
            stmt = stmt.where(self.model.application_id == application_id)
        if version_name:
            stmt = stmt.where(self.model.version_name.like(f'%{version_name}%'))
        if is_active is not None:
            stmt = stmt.where(self.model.is_active == is_active)
        stmt = stmt.order_by(self.model.created_time.desc())
        return await self.select_models(db, stmt)

    def get_select(self, application_id: int = None, version_name: str = None, is_active: bool = None):
        """获取版本查询语句"""
        stmt = select(self.model)
        if application_id:
            stmt = stmt.where(self.model.application_id == application_id)
        if version_name:
            stmt = stmt.where(self.model.version_name.like(f'%{version_name}%'))
        if is_active is not None:
            stmt = stmt.where(self.model.is_active == is_active)
        stmt = stmt.order_by(self.model.created_time.desc())
        return stmt


version_dao: CRUDVersion = CRUDVersion(AppVersion)