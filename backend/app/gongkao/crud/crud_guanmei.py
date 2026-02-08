#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model import GkGuanmei
from backend.app.gongkao.schema.guanmei import CreateGuanmeiParam, UpdateGuanmeiParam


class CRUDGuanmei(CRUDPlus[GkGuanmei]):
    """官媒学言语数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkGuanmei | None:
        """
        获取详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_daily_date(self, db: AsyncSession, daily_date: date) -> Sequence[GkGuanmei]:
        """
        通过日期获取列表

        :param db: 数据库会话
        :param daily_date: 日期
        :return:
        """
        return await self.select_models(db, daily_date=daily_date)

    async def get_select(
        self,
        daily_date: date | None = None,
    ) -> Select:
        """
        获取列表查询表达式

        :param daily_date: 日期
        :return:
        """
        filters = {}
        if daily_date is not None:
            filters['daily_date'] = daily_date
        return await self.select_order('daily_date', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: CreateGuanmeiParam, created_by: int) -> GkGuanmei:
        """
        创建

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        guanmei = await self.create_model(db, obj, created_by=created_by)
        await db.flush()
        await db.refresh(guanmei)
        return guanmei

    async def update(self, db: AsyncSession, pk: int, obj: UpdateGuanmeiParam, updated_by: int) -> int:
        """
        更新

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        return await self.update_model(db, pk, obj, updated_by=updated_by)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        删除（支持批量）

        :param db: 数据库会话
        :param pks: 主键 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def increment_view_count(self, db: AsyncSession, pk: int) -> int:
        """
        增加阅读量

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        guanmei = await self.get(db, pk)
        if guanmei:
            return await self.update_model(db, pk, {'view_count': guanmei.view_count + 1})
        return 0


guanmei_dao: CRUDGuanmei = CRUDGuanmei(GkGuanmei)
