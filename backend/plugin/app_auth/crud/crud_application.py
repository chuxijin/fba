#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.app_auth.model import AppApplication
from backend.plugin.app_auth.schema.application import CreateApplicationParam, UpdateApplicationParam


class CRUDApplication(CRUDPlus[AppApplication]):
    """应用数据库操作类"""

    async def get(self, db: AsyncSession, app_id: int) -> AppApplication | None:
        """
        获取应用详情

        :param db: 数据库会话
        :param app_id: 应用 ID
        :return:
        """
        return await self.select_model(db, app_id)

    async def get_by_app_key(self, db: AsyncSession, app_key: str) -> AppApplication | None:
        """
        通过应用标识获取应用

        :param db: 数据库会话
        :param app_key: 应用标识
        :return:
        """
        return await self.select_model_by_column(db, app_key=app_key)

    async def get_by_name(self, db: AsyncSession, name: str) -> AppApplication | None:
        """
        通过应用名称获取应用

        :param db: 数据库会话
        :param name: 应用名称
        :return:
        """
        return await self.select_model_by_column(db, name=name)

    async def create(self, db: AsyncSession, obj_in: CreateApplicationParam) -> AppApplication:
        """
        创建应用

        :param db: 数据库会话
        :param obj_in: 创建参数
        :return:
        """
        return await self.create_model(db, obj_in)

    async def update(self, db: AsyncSession, app_id: int, obj_in: UpdateApplicationParam) -> int:
        """
        更新应用

        :param db: 数据库会话
        :param app_id: 应用 ID
        :param obj_in: 更新参数
        :return:
        """
        return await self.update_model(db, app_id, obj_in)

    async def delete(self, db: AsyncSession, app_id: int) -> int:
        """删除应用"""
        return await self.delete_model(db, app_id)

    async def get_list(self, db: AsyncSession, name: str = None, status: int = None) -> list[AppApplication]:
        """获取应用列表"""
        stmt = select(self.model)
        if name:
            stmt = stmt.where(self.model.name.like(f'%{name}%'))
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        stmt = stmt.order_by(self.model.created_time.desc())
        result = await db.execute(stmt)
        return result.scalars().all()

    def get_select(self, name: str = None, app_key: str = None, status: int = None):
        """获取应用查询语句"""
        stmt = select(self.model)
        if name:
            stmt = stmt.where(self.model.name.like(f'%{name}%'))
        if app_key:
            stmt = stmt.where(self.model.app_key.like(f'%{app_key}%'))
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        stmt = stmt.order_by(self.model.created_time.desc())
        return stmt


application_dao: CRUDApplication = CRUDApplication(AppApplication)