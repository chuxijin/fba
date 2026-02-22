#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model import GkJingyan
from backend.app.gongkao.schema.jingyan import CreateJingyanParam, UpdateJingyanParam


class CRUDJingyan(CRUDPlus[GkJingyan]):
    """经验数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkJingyan | None:
        """
        获取经验详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_title(self, db: AsyncSession, title: str) -> GkJingyan | None:
        """
        通过标题获取经验

        :param db: 数据库会话
        :param title: 标题
        :return:
        """
        return await self.select_model_by_column(db, title=title)

    async def get_by_category_id(self, db: AsyncSession, category_id: int) -> Sequence[GkJingyan]:
        """
        通过分类获取经验列表

        :param db: 数据库会话
        :param category_id: 分类 ID
        :return:
        """
        return await self.select_models(db, category_id=category_id)

    async def get_by_daily_date(self, db: AsyncSession, daily_date: date) -> Sequence[GkJingyan]:
        """
        通过发布日期获取经验列表

        :param db: 数据库会话
        :param daily_date: 发布日期
        :return:
        """
        return await self.select_models(db, daily_date=daily_date)

    async def get_select(
        self,
        title: str | None = None,
        category_id: int | None = None,
        author: str | None = None,
        tags: str | None = None,
        daily_date: date | None = None,
    ) -> 'Select':
        """
        获取经验列表查询表达式

        :param title: 标题
        :param category_id: 分类 ID
        :param author: 作者
        :param tags: 标签
        :param daily_date: 发布日期
        :return:
        """
        filters = {}
        if title is not None:
            filters['title__like'] = f'%{title}%'
        if category_id is not None:
            filters['category_id'] = category_id
        if author is not None:
            filters['author__like'] = f'%{author}%'
        if tags is not None:
            filters['tags__like'] = f'%{tags}%'
        if daily_date is not None:
            filters['daily_date'] = daily_date
        return await self.select_order('daily_date', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: CreateJingyanParam, created_by: int) -> GkJingyan:
        """
        创建经验

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        jingyan = await self.create_model(db, obj, created_by=created_by)
        await db.flush()
        await db.refresh(jingyan)
        return jingyan

    async def update(self, db: AsyncSession, pk: int, obj: UpdateJingyanParam, updated_by: int) -> int:
        """
        更新经验

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        return await self.update_model(db, pk, obj, updated_by=updated_by)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        删除经验（支持批量）

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
        jingyan = await self.get(db, pk)
        if jingyan:
            return await self.update_model(db, pk, {'view_count': jingyan.view_count + 1})
        return 0


jingyan_dao: CRUDJingyan = CRUDJingyan(GkJingyan)
