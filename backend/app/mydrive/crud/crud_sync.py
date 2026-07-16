#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.mydrive.model.sync import (
    MyDriveSyncConfig,
    MyDriveSyncRule,
    MyDriveSyncRuleSet,
    MyDriveSyncTask,
    MyDriveSyncTaskItem,
)


class CRUDMyDriveSyncRuleSet(CRUDPlus[MyDriveSyncRuleSet]):
    """同步规则集 CRUD"""

    async def get(self, db: AsyncSession, pk: int, owner_id: int) -> MyDriveSyncRuleSet | None:
        """
        获取用户的同步规则集。

        :param db: 数据库会话
        :param pk: 规则集 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        stmt = select(self.model).where(self.model.id == pk, self.model.owner_id == owner_id, self.model.deleted == 0)
        return (await db.execute(stmt)).scalars().first()

    async def get_select(self, owner_id: int) -> Select:
        """
        获取同步规则集查询语句。

        :param owner_id: 所属用户 ID
        :return:
        """
        return select(self.model).where(self.model.owner_id == owner_id, self.model.deleted == 0).order_by(self.model.created_time.desc())

    async def get_by_name(self, db: AsyncSession, owner_id: int, name: str) -> MyDriveSyncRuleSet | None:
        """
        按名称获取同步规则集。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :param name: 规则集名称
        :return:
        """
        stmt = select(self.model).where(
            self.model.owner_id == owner_id,
            self.model.name == name,
            self.model.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()


class CRUDMyDriveSyncRule(CRUDPlus[MyDriveSyncRule]):
    """同步规则 CRUD"""

    async def list_by_rule_set(self, db: AsyncSession, rule_set_id: int) -> list[MyDriveSyncRule]:
        """
        获取规则集中的规则。

        :param db: 数据库会话
        :param rule_set_id: 规则集 ID
        :return:
        """
        stmt = select(self.model).where(self.model.rule_set_id == rule_set_id, self.model.deleted == 0)
        stmt = stmt.order_by(self.model.sort_order, self.model.id)
        return list((await db.execute(stmt)).scalars().all())

    async def replace(self, db: AsyncSession, rule_set_id: int, values: list[dict]) -> None:
        """
        替换规则集中的全部规则。

        :param db: 数据库会话
        :param rule_set_id: 规则集 ID
        :param values: 规则值列表
        :return:
        """
        await db.execute(delete(self.model).where(self.model.rule_set_id == rule_set_id))
        db.add_all([self.model(rule_set_id=rule_set_id, **value) for value in values])


class CRUDMyDriveSyncConfig(CRUDPlus[MyDriveSyncConfig]):
    """同步配置 CRUD"""

    async def get(self, db: AsyncSession, pk: int, owner_id: int) -> MyDriveSyncConfig | None:
        """
        获取用户的同步配置。

        :param db: 数据库会话
        :param pk: 同步配置 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        stmt = select(self.model).where(self.model.id == pk, self.model.owner_id == owner_id, self.model.deleted == 0)
        return (await db.execute(stmt)).scalars().first()

    async def get_select(self, owner_id: int) -> Select:
        """
        获取同步配置查询语句。

        :param owner_id: 所属用户 ID
        :return:
        """
        return select(self.model).where(self.model.owner_id == owner_id, self.model.deleted == 0).order_by(self.model.created_time.desc())

    async def list_enabled_cron_configs(self, db: AsyncSession) -> list[MyDriveSyncConfig]:
        """获取启用定时同步的配置。"""
        stmt = select(self.model).where(
            self.model.is_enabled.is_(True),
            self.model.cron.is_not(None),
            self.model.cron != '',
            self.model.deleted == 0,
        )
        return list((await db.execute(stmt)).scalars().all())


class CRUDMyDriveSyncTask(CRUDPlus[MyDriveSyncTask]):
    """同步任务 CRUD"""

    async def get(self, db: AsyncSession, pk: int, owner_id: int) -> MyDriveSyncTask | None:
        """
        获取用户的同步任务。

        :param db: 数据库会话
        :param pk: 同步任务 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        stmt = (
            select(self.model)
            .join(MyDriveSyncConfig, MyDriveSyncConfig.id == self.model.config_id)
            .where(self.model.id == pk, MyDriveSyncConfig.owner_id == owner_id, self.model.deleted == 0)
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_select(self, owner_id: int, config_id: int | None = None) -> Select:
        """
        获取同步任务查询语句。

        :param owner_id: 所属用户 ID
        :param config_id: 同步配置 ID
        :return:
        """
        stmt = (
            select(self.model)
            .join(MyDriveSyncConfig, MyDriveSyncConfig.id == self.model.config_id)
            .where(MyDriveSyncConfig.owner_id == owner_id, self.model.deleted == 0)
        )
        if config_id is not None:
            stmt = stmt.where(self.model.config_id == config_id)
        return stmt.order_by(self.model.created_time.desc())

    async def has_active_task(self, db: AsyncSession, config_id: int) -> bool:
        """
        判断同步配置是否存在活动任务。

        :param db: 数据库会话
        :param config_id: 同步配置 ID
        :return:
        """
        stmt = select(self.model.id).where(
            self.model.config_id == config_id,
            self.model.status.in_({'pending', 'running'}),
            self.model.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first() is not None


class CRUDMyDriveSyncTaskItem(CRUDPlus[MyDriveSyncTaskItem]):
    """同步任务项 CRUD"""

    async def get_select(self, task_id: int) -> Select:
        """
        获取同步任务项查询语句。

        :param task_id: 同步任务 ID
        :return:
        """
        return select(self.model).where(self.model.task_id == task_id, self.model.deleted == 0).order_by(self.model.id)


mydrive_sync_rule_set_dao: CRUDMyDriveSyncRuleSet = CRUDMyDriveSyncRuleSet(MyDriveSyncRuleSet)
mydrive_sync_rule_dao: CRUDMyDriveSyncRule = CRUDMyDriveSyncRule(MyDriveSyncRule)
mydrive_sync_config_dao: CRUDMyDriveSyncConfig = CRUDMyDriveSyncConfig(MyDriveSyncConfig)
mydrive_sync_task_dao: CRUDMyDriveSyncTask = CRUDMyDriveSyncTask(MyDriveSyncTask)
mydrive_sync_task_item_dao: CRUDMyDriveSyncTaskItem = CRUDMyDriveSyncTaskItem(MyDriveSyncTaskItem)
