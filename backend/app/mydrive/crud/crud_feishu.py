#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.mydrive.model.feishu import FeishuSheetConfig, FeishuSheetTask


class CRUDFeishuSheetConfig(CRUDPlus[FeishuSheetConfig]):
    """飞书表格导出配置 CRUD"""

    async def get(self, db: AsyncSession, pk: int) -> FeishuSheetConfig | None:
        """
        获取导出配置。

        :param db: 数据库会话
        :param pk: 导出配置 ID
        :return:
        """
        stmt = select(self.model).where(self.model.id == pk, self.model.deleted == 0)
        return (await db.execute(stmt)).scalars().first()

    async def get_select(self, name: str | None = None, is_enabled: bool | None = None) -> Select:
        """
        获取导出配置查询语句。

        :param name: 配置名称（模糊匹配）
        :param is_enabled: 是否启用
        :return:
        """
        stmt = select(self.model).where(self.model.deleted == 0)
        if name:
            stmt = stmt.where(self.model.name.ilike(f'%{name}%'))
        if is_enabled is not None:
            stmt = stmt.where(self.model.is_enabled.is_(is_enabled))
        return stmt.order_by(self.model.created_time.desc())

    async def get_by_name(self, db: AsyncSession, name: str) -> FeishuSheetConfig | None:
        """
        按名称获取导出配置。

        :param db: 数据库会话
        :param name: 配置名称
        :return:
        """
        stmt = select(self.model).where(self.model.name == name, self.model.deleted == 0)
        return (await db.execute(stmt)).scalars().first()

    async def list_enabled_cron_configs(self, db: AsyncSession) -> list[FeishuSheetConfig]:
        """获取启用定时导出的配置。"""
        stmt = select(self.model).where(
            self.model.is_enabled.is_(True),
            self.model.cron.is_not(None),
            self.model.cron != '',
            self.model.deleted == 0,
        )
        return list((await db.execute(stmt)).scalars().all())


class CRUDFeishuSheetTask(CRUDPlus[FeishuSheetTask]):
    """飞书表格导出任务 CRUD"""

    async def get(self, db: AsyncSession, pk: int) -> FeishuSheetTask | None:
        """
        获取导出任务。

        :param db: 数据库会话
        :param pk: 导出任务 ID
        :return:
        """
        stmt = select(self.model).where(self.model.id == pk, self.model.deleted == 0)
        return (await db.execute(stmt)).scalars().first()

    async def get_select(self, config_id: int | None = None, status: str | None = None) -> Select:
        """
        获取导出任务查询语句。

        :param config_id: 导出配置 ID
        :param status: 任务状态
        :return:
        """
        stmt = select(self.model).where(self.model.deleted == 0)
        if config_id is not None:
            stmt = stmt.where(self.model.config_id == config_id)
        if status:
            stmt = stmt.where(self.model.status == status)
        return stmt.order_by(self.model.created_time.desc())

    async def has_active_task(self, db: AsyncSession, config_id: int) -> bool:
        """
        判断导出配置是否存在活动任务。

        :param db: 数据库会话
        :param config_id: 导出配置 ID
        :return:
        """
        stmt = select(self.model.id).where(
            self.model.config_id == config_id,
            self.model.status.in_({'pending', 'running'}),
            self.model.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first() is not None


feishu_sheet_config_dao: CRUDFeishuSheetConfig = CRUDFeishuSheetConfig(FeishuSheetConfig)
feishu_sheet_task_dao: CRUDFeishuSheetTask = CRUDFeishuSheetTask(FeishuSheetTask)
