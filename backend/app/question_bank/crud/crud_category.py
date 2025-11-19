#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import ExamCategory
from backend.app.question_bank.schema.category import CreateCategoryParam, UpdateCategoryParam


class CRUDCategory(CRUDPlus[ExamCategory]):
    """分类数据库操作类"""

    async def get(self, db: AsyncSession, category_id: int) -> ExamCategory | None:
        """
        获取分类详情

        :param db: 数据库会话
        :param category_id: 分类 ID
        :return:
        """
        return await self.select_model_by_column(db, id=category_id)

    async def get_by_code(self, db: AsyncSession, code: str) -> ExamCategory | None:
        """
        通过编码获取分类

        :param db: 数据库会话
        :param code: 分类编码
        :return:
        """
        return await self.select_model_by_column(db, code=code)

    async def get_all(
        self,
        db: AsyncSession,
        cat_type: int | None = None,
        is_active: bool | None = None,
    ) -> Sequence[ExamCategory]:
        """
        获取所有分类

        :param db: 数据库会话
        :param cat_type: 分类类型
        :param is_active: 是否启用
        :return:
        """
        filters = {}

        if cat_type is not None:
            filters['cat_type'] = cat_type
        if is_active is not None:
            filters['is_active'] = is_active

        return await self.select_models_order(db, 'sort_order', 'asc', **filters)

    async def get_children(self, db: AsyncSession, parent_id: int) -> Sequence[ExamCategory]:
        """
        获取子分类列表

        :param db: 数据库会话
        :param parent_id: 父级分类 ID
        :return:
        """
        return await self.select_models(db, parent_id=parent_id)

    async def create(self, db: AsyncSession, obj: CreateCategoryParam) -> None:
        """
        创建分类

        :param db: 数据库会话
        :param obj: 创建分类参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, category_id: int, obj: UpdateCategoryParam) -> int:
        """
        更新分类

        :param db: 数据库会话
        :param category_id: 分类 ID
        :param obj: 更新分类参数
        :return:
        """
        return await self.update_model(db, category_id, obj)

    async def delete(self, db: AsyncSession, category_ids: list[int]) -> int:
        """
        批量删除分类

        :param db: 数据库会话
        :param category_ids: 分类 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=category_ids)


category_dao: CRUDCategory = CRUDCategory(ExamCategory)
