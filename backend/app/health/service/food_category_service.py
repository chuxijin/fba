#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.health.crud.crud_food_category import food_category_dao
from backend.app.health.model import FoodCategory
from backend.app.health.schema.food_category import CreateFoodCategoryParam, UpdateFoodCategoryParam
from backend.common.exception import errors
from backend.utils.build_tree import get_tree_data


class FoodCategoryService:
    """食物分类服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> FoodCategory:
        """
        获取食物分类详情

        :param db: 数据库会话
        :param pk: 分类 ID
        :return:
        """
        category = await food_category_dao.get(db, pk)
        if not category:
            raise errors.NotFoundError(msg='食物分类不存在')
        return category

    @staticmethod
    async def get_tree(*, db: AsyncSession, name: str | None, status: int | None) -> list[dict[str, Any]]:
        """
        获取食物分类树形结构

        :param db: 数据库会话
        :param name: 分类名称
        :param status: 状态
        :return:
        """
        categories = await food_category_dao.get_all(db, name, status)
        tree_data = get_tree_data(categories)
        return tree_data

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateFoodCategoryParam) -> None:
        """
        创建食物分类

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        category = await food_category_dao.get_by_name(db, obj.name)
        if category:
            raise errors.ConflictError(msg='分类名称已存在')
        if obj.parent_id is not None:
            parent_category = await food_category_dao.get(db, obj.parent_id)
            if not parent_category:
                raise errors.NotFoundError(msg='父级分类不存在')
        await food_category_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateFoodCategoryParam) -> int:
        """
        更新食物分类

        :param db: 数据库会话
        :param pk: 分类 ID
        :param obj: 更新参数
        :return:
        """
        category = await food_category_dao.get(db, pk)
        if not category:
            raise errors.NotFoundError(msg='食物分类不存在')
        if category.name != obj.name and await food_category_dao.get_by_name(db, obj.name):
            raise errors.ConflictError(msg='分类名称已存在')
        if obj.parent_id:
            if obj.parent_id == category.id:
                raise errors.ForbiddenError(msg='禁止关联自身为父级')
            parent_category = await food_category_dao.get(db, obj.parent_id)
            if not parent_category:
                raise errors.NotFoundError(msg='父级分类不存在')
        count = await food_category_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除食物分类

        :param db: 数据库会话
        :param pk: 分类 ID
        :return:
        """
        category = await food_category_dao.get(db, pk)
        if not category:
            raise errors.NotFoundError(msg='食物分类不存在')
        children = await food_category_dao.get_children(db, pk)
        if children:
            raise errors.ConflictError(msg='分类下存在子分类，无法删除')
        count = await food_category_dao.delete(db, pk)
        return count


food_category_service: FoodCategoryService = FoodCategoryService()
