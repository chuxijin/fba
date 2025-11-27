#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.health.model import FoodCategory
from backend.app.health.schema.food_category import CreateFoodCategoryParam, UpdateFoodCategoryParam


class CRUDFoodCategory(CRUDPlus[FoodCategory]):
    """食物分类数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> FoodCategory | None:
        """
        获取食物分类详情

        :param db: 数据库会话
        :param pk: 分类 ID
        :return:
        """
        return await self.select_model_by_column(db, id=pk, del_flag=False)

    async def get_by_name(self, db: AsyncSession, name: str) -> FoodCategory | None:
        """
        通过名称获取食物分类

        :param db: 数据库会话
        :param name: 分类名称
        :return:
        """
        return await self.select_model_by_column(db, name=name, del_flag=False)

    async def get_all(
        self, db: AsyncSession, name: str | None, status: int | None
    ) -> Sequence[FoodCategory]:
        """
        获取所有食物分类

        :param db: 数据库会话
        :param name: 分类名称
        :param status: 状态
        :return:
        """
        filters = {'del_flag': False}
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if status is not None:
            filters['status'] = status
        return await self.select_models_order(db, 'sort', 'asc', **filters)

    async def create(self, db: AsyncSession, obj: CreateFoodCategoryParam) -> None:
        """
        创建食物分类

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateFoodCategoryParam) -> int:
        """
        更新食物分类

        :param db: 数据库会话
        :param pk: 分类 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除食物分类

        :param db: 数据库会话
        :param pk: 分类 ID
        :return:
        """
        return await self.delete_model_by_column(db, id=pk, logical_deletion=True, deleted_flag_column='del_flag')

    async def get_children(self, db: AsyncSession, pk: int) -> Sequence[FoodCategory]:
        """
        获取子分类列表

        :param db: 数据库会话
        :param pk: 分类 ID
        :return:
        """
        return await self.select_models(db, parent_id=pk, del_flag=False)


food_category_dao: CRUDFoodCategory = CRUDFoodCategory(FoodCategory)
