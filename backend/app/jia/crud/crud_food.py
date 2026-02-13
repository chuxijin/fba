#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.jia.model.food import HealthyFood
from backend.app.jia.schema.food import CreateFoodParam, UpdateFoodParam


class CRUDFood(CRUDPlus[HealthyFood]):
    """食物数据操作类"""

    async def get(self, db: AsyncSession, pk: int) -> HealthyFood | None:
        """
        通过主键获取食物详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_name(self, db: AsyncSession, name: str) -> HealthyFood | None:
        """
        通过名称获取食物详情

        :param db: 数据库会话
        :param name: 食物名称
        :return:
        """
        return await self.select_model_by_column(db, name=name)

    async def get_by_barcode(self, db: AsyncSession, barcode: str) -> HealthyFood | None:
        """
        通过条形码获取食物详情

        :param db: 数据库会话
        :param barcode: 条形码
        :return:
        """
        if not barcode:
            return None
        return await self.select_model_by_column(db, barcode=barcode)

    async def get_list(
        self,
        name: str | None = None,
        category_id: int | None = None,
        status: bool | None = None,
    ) -> Select:
        """
        获取食物列表查询表达式（供分页使用）

        :param name: 名称关键词
        :param category_id: 分类 ID
        :param status: 状态
        :return:
        """
        filters = {}
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if category_id is not None:
            filters['category_id'] = category_id
        if status is not None:
            filters['status'] = status

        return await self.select_order('id', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: CreateFoodParam, vector: list[float] | None = None) -> HealthyFood:
        """
        创建食物

        :param db: 数据库会话
        :param obj: 创建参数
        :param vector: 向量
        :return:
        """
        data = obj.model_dump()
        if vector:
            data['vector'] = vector
        return await self.create_model(db, data)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateFoodParam, vector: list[float] | None = None) -> int:
        """
        更新食物

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :param vector: 向量
        :return:
        """
        update_data = obj.model_dump(exclude_unset=True)
        if vector:
            update_data['vector'] = vector
        return await self.update_model(db, pk, update_data)

    async def delete(self, db: AsyncSession, pk: list[int]) -> int:
        """
        删除食物

        :param db: 数据库会话
        :param pk: 主键 ID 列表
        :return:
        """
        return await self.delete_model(db, pk)

    async def search_by_vector(self, db: AsyncSession, vector: list, limit: int = 5) -> Sequence[HealthyFood]:
        """
        根据向量搜索相似食物
        
        :param db: 数据库会话
        :param vector: 向量
        :param limit: 返回数量
        :return:
        """
        from sqlalchemy import select
        # 使用 pgvector 的 L2 距离操作符 <->
        stmt = select(HealthyFood).order_by(HealthyFood.vector.l2_distance(vector)).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()


food_dao: CRUDFood = CRUDFood(HealthyFood)
