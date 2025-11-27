#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.health.model import Food
from backend.app.health.schema.food import CreateFoodParam, UpdateFoodParam


class CRUDFood(CRUDPlus[Food]):
    """食物数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> Food | None:
        """
        获取食物详情

        :param db: 数据库会话
        :param pk: 食物 ID
        :return:
        """
        return await self.select_model_by_column(db, id=pk, del_flag=False)

    async def get_by_name(self, db: AsyncSession, name: str) -> Food | None:
        """
        通过名称获取食物

        :param db: 数据库会话
        :param name: 食物名称
        :return:
        """
        return await self.select_model_by_column(db, name=name, del_flag=False)

    async def get_select(
        self,
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
        filters = {}
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if category_id is not None:
            filters['category_id'] = category_id
        if food_type is not None:
            filters['food_type'] = food_type
        if processing_level is not None:
            filters['processing_level'] = processing_level
        if status is not None:
            filters['status'] = status
        return (
            select(self.model)
            .where(self.model.del_flag == False)  # noqa: E712
            .filter_by(**filters)
            .order_by(self.model.created_time.desc())
        )

    async def create(self, db: AsyncSession, obj: CreateFoodParam) -> None:
        """
        创建食物

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateFoodParam) -> int:
        """
        更新食物

        :param db: 数据库会话
        :param pk: 食物 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除食物

        :param db: 数据库会话
        :param pk: 食物 ID
        :return:
        """
        return await self.delete_model_by_column(db, id=pk, logical_deletion=True, deleted_flag_column='del_flag')


food_dao: CRUDFood = CRUDFood(Food)
