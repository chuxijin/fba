#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_category import category_dao
from backend.app.question_bank.model import ExamCategory
from backend.app.question_bank.schema.category import CreateCategoryParam, DeleteCategoryParam, UpdateCategoryParam
from backend.common.exception import errors
from backend.utils.build_tree import get_tree_data


class CategoryService:
    """分类服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> ExamCategory:
        """
        获取分类详情

        :param db: 数据库会话
        :param pk: 分类 ID
        :return:
        """
        category = await category_dao.get(db, pk)
        if not category:
            raise errors.NotFoundError(msg='分类不存在')
        return category

    @staticmethod
    async def get_tree(
        *,
        db: AsyncSession,
        cat_type: int | None = None,
        is_active: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取分类树形结构

        :param db: 数据库会话
        :param cat_type: 分类类型
        :param is_active: 是否启用
        :return:
        """
        category_select = await category_dao.get_all(db, cat_type, is_active)
        tree_data = get_tree_data(category_select, sort_key='sort_order')
        return tree_data

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateCategoryParam) -> None:
        """
        创建分类

        :param db: 数据库会话
        :param obj: 创建分类参数
        :return:
        """
        category = await category_dao.get_by_code(db, obj.code)
        if category:
            raise errors.ConflictError(msg='分类编码已存在')
        if obj.parent_id:
            parent_category = await category_dao.get(db, obj.parent_id)
            if not parent_category:
                raise errors.NotFoundError(msg='父级分类不存在')
        await category_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateCategoryParam) -> int:
        """
        更新分类

        :param db: 数据库会话
        :param pk: 分类 ID
        :param obj: 更新分类参数
        :return:
        """
        category = await category_dao.get(db, pk)
        if not category:
            raise errors.NotFoundError(msg='分类不存在')
        if category.code != obj.code and await category_dao.get_by_code(db, obj.code):
            raise errors.ConflictError(msg='分类编码已存在')
        if obj.parent_id:
            parent_category = await category_dao.get(db, obj.parent_id)
            if not parent_category:
                raise errors.NotFoundError(msg='父级分类不存在')
        if obj.parent_id == category.id:
            raise errors.ForbiddenError(msg='禁止关联自身为父级')
        count = await category_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteCategoryParam) -> int:
        """
        删除分类

        :param db: 数据库会话
        :param obj: 删除分类参数
        :return:
        """
        for category_id in obj.ids:
            children = await category_dao.get_children(db, category_id)
            if children:
                raise errors.ConflictError(msg='分类下存在子分类，无法删除')
        count = await category_dao.delete(db, obj.ids)
        return count


category_service: CategoryService = CategoryService()
