#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model.category import GkCategory
from backend.app.gongkao.schema.category import CreateCategoryParam, UpdateCategoryParam


class CRUDCategory(CRUDPlus[GkCategory]):
    """分类数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkCategory | None:
        """
        获取分类详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_name_and_type(self, db: AsyncSession, name: str, type: str) -> GkCategory | None:
        """
        通过名称和类型获取分类

        :param db: 数据库会话
        :param name: 分类名称
        :param type: 分类类型
        :return:
        """
        return await self.select_model_by_column(db, name=name, type=type)

    async def get_children(self, db: AsyncSession, parent_id: int) -> Sequence[GkCategory]:
        """
        获取子分类列表

        :param db: 数据库会话
        :param parent_id: 父级分类 ID
        :return:
        """
        return await self.select_models_order(db, 'sort_order', 'asc', parent_id=parent_id)

    async def get_select(
        self,
        name: str | None = None,
        type: str | None = None,
        parent_id: int | None = None,
        status: bool | None = None,
    ) -> 'Select':
        """
        获取分类列表查询表达式

        :param name: 分类名称
        :param type: 分类类型
        :param parent_id: 父级分类 ID
        :param status: 状态
        :return:
        """
        filters = {}
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if type is not None:
            filters['type'] = type
        if parent_id is not None:
            filters['parent_id'] = parent_id
        if status is not None:
            filters['status'] = status
        return await self.select_order('sort_order', 'asc', **filters)

    async def create(self, db: AsyncSession, obj: CreateCategoryParam, created_by: int) -> GkCategory:
        """
        创建分类

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        category = await self.create_model(db, obj, created_by=created_by)
        await db.flush()
        await db.refresh(category)
        return category

    async def update(self, db: AsyncSession, pk: int, obj: UpdateCategoryParam, updated_by: int) -> int:
        """
        更新分类

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        return await self.update_model(db, pk, obj, updated_by=updated_by)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        删除分类（支持批量）

        :param db: 数据库会话
        :param pks: 主键 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)


category_dao: CRUDCategory = CRUDCategory(GkCategory)
