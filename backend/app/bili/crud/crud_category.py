#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.bili.model import BiliCategory
from backend.app.bili.schema.category import CreateBiliCategoryParam, UpdateBiliCategoryParam


class CRUDBiliCategory(CRUDPlus[BiliCategory]):
    """B 站分类数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> BiliCategory | None:
        """
        获取分类详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_name(self, db: AsyncSession, name: str) -> BiliCategory | None:
        """
        通过名称获取分类

        :param db: 数据库会话
        :param name: 分类名称
        :return:
        """
        return await self.select_model_by_column(db, name=name)

    async def get_list(
        self,
        db: AsyncSession,
        name: str | None = None,
        status: int | None = None,
        parent_id: int | None = None,
    ) -> Sequence[BiliCategory]:
        """
        获取分类列表

        :param db: 数据库会话
        :param name: 分类名称
        :param status: 状态
        :param parent_id: 父分类 ID
        :return:
        """
        filters = {}
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if status is not None:
            filters['status'] = status
        if parent_id is not None:
            filters['parent_id'] = parent_id
        return await self.select_models_order(db, 'sort', 'desc', **filters)

    async def get_children(self, db: AsyncSession, parent_id: int) -> Sequence[BiliCategory]:
        """
        获取子分类列表

        :param db: 数据库会话
        :param parent_id: 父分类 ID
        :return:
        """
        return await self.select_models(db, parent_id=parent_id)

    async def create(self, db: AsyncSession, obj: CreateBiliCategoryParam) -> None:
        """
        创建分类

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateBiliCategoryParam) -> int:
        """
        更新分类

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除分类

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.delete_model(db, pk)


bili_category_dao: CRUDBiliCategory = CRUDBiliCategory(BiliCategory)
