#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.health.crud.crud_food import food_dao
from backend.app.health.crud.crud_nutrition_fact import nutrition_fact_dao
from backend.app.health.model import NutritionFact
from backend.app.health.schema.nutrition_fact import CreateNutritionFactParam, UpdateNutritionFactParam
from backend.common.exception import errors


class NutritionFactService:
    """营养成分服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> NutritionFact:
        """
        获取营养成分详情

        :param db: 数据库会话
        :param pk: 营养成分 ID
        :return:
        """
        nutrition_fact = await nutrition_fact_dao.get(db, pk)
        if not nutrition_fact:
            raise errors.NotFoundError(msg='营养成分不存在')
        return nutrition_fact

    @staticmethod
    async def get_by_food_id(*, db: AsyncSession, food_id: int) -> NutritionFact:
        """
        通过食物 ID 获取营养成分

        :param db: 数据库会话
        :param food_id: 食物 ID
        :return:
        """
        nutrition_fact = await nutrition_fact_dao.get_by_food_id(db, food_id)
        if not nutrition_fact:
            raise errors.NotFoundError(msg='营养成分不存在')
        return nutrition_fact

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateNutritionFactParam) -> None:
        """
        创建营养成分

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        food = await food_dao.get(db, obj.food_id)
        if not food:
            raise errors.NotFoundError(msg='食物不存在')
        existing = await nutrition_fact_dao.get_by_food_id(db, obj.food_id)
        if existing:
            raise errors.ConflictError(msg='该食物的营养成分已存在')
        await nutrition_fact_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateNutritionFactParam) -> int:
        """
        更新营养成分

        :param db: 数据库会话
        :param pk: 营养成分 ID
        :param obj: 更新参数
        :return:
        """
        nutrition_fact = await nutrition_fact_dao.get(db, pk)
        if not nutrition_fact:
            raise errors.NotFoundError(msg='营养成分不存在')
        food = await food_dao.get(db, obj.food_id)
        if not food:
            raise errors.NotFoundError(msg='食物不存在')
        if nutrition_fact.food_id != obj.food_id:
            existing = await nutrition_fact_dao.get_by_food_id(db, obj.food_id)
            if existing:
                raise errors.ConflictError(msg='目标食物已有营养成分记录')
        count = await nutrition_fact_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除营养成分

        :param db: 数据库会话
        :param pk: 营养成分 ID
        :return:
        """
        nutrition_fact = await nutrition_fact_dao.get(db, pk)
        if not nutrition_fact:
            raise errors.NotFoundError(msg='营养成分不存在')
        count = await nutrition_fact_dao.delete(db, pk)
        return count


nutrition_fact_service: NutritionFactService = NutritionFactService()
