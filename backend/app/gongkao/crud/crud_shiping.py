#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model import GkShiping
from backend.app.gongkao.schema.shiping import CreateShipingParam, UpdateShipingParam


class CRUDShiping(CRUDPlus[GkShiping]):
    """时评数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkShiping | None:
        """
        获取时评详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_title(self, db: AsyncSession, title: str) -> GkShiping | None:
        """
        通过标题获取时评

        :param db: 数据库会话
        :param title: 标题
        :return:
        """
        return await self.select_model_by_column(db, title=title)

    async def get_by_daily_date(self, db: AsyncSession, daily_date: date) -> Sequence[GkShiping]:
        """
        通过每日时间获取时评列表

        :param db: 数据库会话
        :param daily_date: 每日时间
        :return:
        """
        return await self.select_models(db, daily_date=daily_date)

    async def get_select(
        self,
        title: str | None = None,
        source: str | None = None,
        author: str | None = None,
        keywords: str | None = None,
        daily_date: date | None = None,
    ) -> 'Select':
        """
        获取时评列表查询表达式

        :param title: 标题
        :param source: 来源
        :param author: 作者
        :param keywords: 关键词
        :param daily_date: 每日时间
        :return:
        """
        filters = {}
        if title is not None:
            filters['title__like'] = f'%{title}%'
        if source is not None:
            filters['source__like'] = f'%{source}%'
        if author is not None:
            filters['author__like'] = f'%{author}%'
        if keywords is not None:
            filters['keywords__like'] = f'%{keywords}%'
        if daily_date is not None:
            filters['daily_date'] = daily_date
        return await self.select_order('daily_date', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: CreateShipingParam, created_by: int) -> GkShiping:
        """
        创建时评

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        shiping = await self.create_model(db, obj, created_by=created_by)
        await db.flush()
        await db.refresh(shiping)
        return shiping

    async def update(self, db: AsyncSession, pk: int, obj: UpdateShipingParam, updated_by: int) -> int:
        """
        更新时评

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        return await self.update_model(db, pk, obj, updated_by=updated_by)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        删除时评（支持批量）

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
        shiping = await self.get(db, pk)
        if shiping:
            return await self.update_model(db, pk, {'view_count': shiping.view_count + 1})
        return 0


shiping_dao: CRUDShiping = CRUDShiping(GkShiping)
