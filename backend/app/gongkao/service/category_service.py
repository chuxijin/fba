#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_category import category_dao
from backend.app.gongkao.model.category import GkCategory
from backend.app.gongkao.schema.category import (
    CategoryParam,
    CreateCategoryParam,
    DeleteCategoryParam,
    UpdateCategoryParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.build_tree import get_tree_data


class CategoryService:
    """分类服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkCategory:
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
    async def get_list(*, db: AsyncSession, params: CategoryParam) -> dict[str, Any]:
        """
        获取分类列表（分页）

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        category_select = await category_dao.get_select(
            name=params.name,
            type=params.type,
            parent_id=params.parent_id,
            status=params.status,
        )
        return await paging_data(db, category_select)

    @staticmethod
    async def get_all(*, db: AsyncSession, params: CategoryParam) -> Sequence[GkCategory]:
        """
        获取所有分类列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        category_select = await category_dao.get_select(
            name=params.name,
            type=params.type,
            parent_id=params.parent_id,
            status=params.status,
        )
        return (await db.execute(category_select)).scalars().all()

    @staticmethod
    async def get_tree(*, db: AsyncSession, params: CategoryParam) -> list[dict[str, Any]]:
        """
        获取分类树形结构

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        category_select = await category_dao.get_select(
            name=params.name,
            type=params.type,
            parent_id=params.parent_id,
            status=params.status,
        )
        category_data = (await db.execute(category_select)).scalars().all()
        return get_tree_data(category_data, sort_key='sort_order')

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateCategoryParam, created_by: int) -> GkCategory:
        """
        创建分类

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        category = await category_dao.get_by_name_and_type(db, obj.name, obj.type)
        if category:
            raise errors.ConflictError(msg='该类型下分类名称已存在')
        return await category_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateCategoryParam, updated_by: int) -> int:
        """
        更新分类

        :param db: 数据库会话
        :param pk: 分类 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        category = await category_dao.get(db, pk)
        if not category:
            raise errors.NotFoundError(msg='分类不存在')
        if obj.name and obj.type and (category.name != obj.name or category.type != obj.type):
            existing = await category_dao.get_by_name_and_type(db, obj.name, obj.type)
            if existing:
                raise errors.ConflictError(msg='该类型下分类名称已存在')
        return await category_dao.update(db, pk, obj, updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteCategoryParam) -> int:
        """
        删除分类

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await category_dao.delete(db, obj.ids)


category_service: CategoryService = CategoryService()
