#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model.shizhen import GkShizhen
from backend.app.gongkao.schema.shizhen import CreateShizhenParam, UpdateShizhenParam


class CRUDShizhen(CRUDPlus[GkShizhen]):
    """时政数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkShizhen | None:
        """
        获取时政详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_date(self, db: AsyncSession, daily_date: date) -> GkShizhen | None:
        """
        通过日期获取时政

        :param db: 数据库会话
        :param daily_date: 日期
        :return:
        """
        return await self.select_model_by_column(db, daily_date=daily_date)

    async def get_select(self, daily_date: date | None = None) -> 'Select':
        """
        获取时政列表查询表达式

        :param daily_date: 日期
        :return:
        """
        filters = {}
        if daily_date is not None:
            filters['daily_date'] = daily_date
        return await self.select_order('daily_date', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: CreateShizhenParam, created_by: int) -> GkShizhen:
        """
        创建时政

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        shizhen = await self.create_model(db, obj, created_by=created_by)
        await db.flush()
        await db.refresh(shizhen)
        return shizhen

    async def update(self, db: AsyncSession, pk: int, obj: UpdateShizhenParam, updated_by: int) -> int:
        """
        更新时政

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        return await self.update_model(db, pk, obj, updated_by=updated_by)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        删除时政

        :param db: 数据库会话
        :param pks: 主键 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)


shizhen_dao: CRUDShizhen = CRUDShizhen(GkShizhen)
