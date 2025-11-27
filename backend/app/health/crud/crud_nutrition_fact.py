#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.health.model import NutritionFact
from backend.app.health.schema.nutrition_fact import CreateNutritionFactParam, UpdateNutritionFactParam


class CRUDNutritionFact(CRUDPlus[NutritionFact]):
    """营养成分数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> NutritionFact | None:
        """
        获取营养成分详情

        :param db: 数据库会话
        :param pk: 营养成分 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_food_id(self, db: AsyncSession, food_id: int) -> NutritionFact | None:
        """
        通过食物 ID 获取营养成分

        :param db: 数据库会话
        :param food_id: 食物 ID
        :return:
        """
        return await self.select_model_by_column(db, food_id=food_id)

    async def create(self, db: AsyncSession, obj: CreateNutritionFactParam) -> None:
        """
        创建营养成分

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateNutritionFactParam) -> int:
        """
        更新营养成分

        :param db: 数据库会话
        :param pk: 营养成分 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def update_by_food_id(self, db: AsyncSession, food_id: int, obj: UpdateNutritionFactParam) -> int:
        """
        通过食物 ID 更新营养成分

        :param db: 数据库会话
        :param food_id: 食物 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model_by_column(db, obj, food_id=food_id)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除营养成分

        :param db: 数据库会话
        :param pk: 营养成分 ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def delete_by_food_id(self, db: AsyncSession, food_id: int) -> int:
        """
        通过食物 ID 删除营养成分

        :param db: 数据库会话
        :param food_id: 食物 ID
        :return:
        """
        return await self.delete_model_by_column(db, food_id=food_id)


nutrition_fact_dao: CRUDNutritionFact = CRUDNutritionFact(NutritionFact)
