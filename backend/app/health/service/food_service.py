#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.health.crud.crud_food import food_dao
from backend.app.health.crud.crud_food_category import food_category_dao
from backend.app.health.model import Food
from backend.app.health.schema.food import CreateFoodParam, UpdateFoodParam
from backend.common.exception import errors


class FoodService:
    """食物服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Food:
        """
        获取食物详情

        :param db: 数据库会话
        :param pk: 食物 ID
        :return:
        """
        food = await food_dao.get(db, pk)
        if not food:
            raise errors.NotFoundError(msg='食物不存在')
        return food

    @staticmethod
    async def get_select(
        *,
        name: str | None,
        category_id: int | None,
        food_type: int | None,
        processing_level: int | None,
        status: int | None,
    ) -> Select:
        """
        获取食物列表查询表达式

        :param name: 食物名称
        :param category_id: 分类 ID
        :param food_type: 食物类型
        :param processing_level: 加工程度
        :param status: 状态
        :return:
        """
        return await food_dao.get_select(name, category_id, food_type, processing_level, status)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateFoodParam) -> None:
        """
        创建食物

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        food = await food_dao.get_by_name(db, obj.name)
        if food:
            raise errors.ConflictError(msg='食物名称已存在')
        category = await food_category_dao.get(db, obj.category_id)
        if not category:
            raise errors.NotFoundError(msg='食物分类不存在')
        await food_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateFoodParam) -> int:
        """
        更新食物

        :param db: 数据库会话
        :param pk: 食物 ID
        :param obj: 更新参数
        :return:
        """
        food = await food_dao.get(db, pk)
        if not food:
            raise errors.NotFoundError(msg='食物不存在')
        if food.name != obj.name and await food_dao.get_by_name(db, obj.name):
            raise errors.ConflictError(msg='食物名称已存在')
        category = await food_category_dao.get(db, obj.category_id)
        if not category:
            raise errors.NotFoundError(msg='食物分类不存在')
        count = await food_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除食物

        :param db: 数据库会话
        :param pk: 食物 ID
        :return:
        """
        food = await food_dao.get(db, pk)
        if not food:
            raise errors.NotFoundError(msg='食物不存在')
        count = await food_dao.delete(db, pk)
        return count


food_service: FoodService = FoodService()
