#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.health.model import FoodTag, FoodTagRelation
from backend.app.health.schema.food_tag import CreateFoodTagParam, UpdateFoodTagParam


class CRUDFoodTag(CRUDPlus[FoodTag]):
    """食物标签数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> FoodTag | None:
        """
        获取食物标签详情

        :param db: 数据库会话
        :param pk: 标签 ID
        :return:
        """
        return await self.select_model_by_column(db, id=pk, del_flag=False)

    async def get_by_name(self, db: AsyncSession, name: str) -> FoodTag | None:
        """
        通过名称获取食物标签

        :param db: 数据库会话
        :param name: 标签名称
        :return:
        """
        return await self.select_model_by_column(db, name=name, del_flag=False)

    async def get_select(
        self, name: str | None, tag_group: int | None, status: int | None
    ) -> Select:
        """
        获取食物标签列表查询表达式

        :param name: 标签名称
        :param tag_group: 标签分组
        :param status: 状态
        :return:
        """
        filters = {}
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if tag_group is not None:
            filters['tag_group'] = tag_group
        if status is not None:
            filters['status'] = status
        return (
            select(self.model)
            .where(self.model.del_flag == False)  # noqa: E712
            .filter_by(**filters)
            .order_by(self.model.sort.asc())
        )

    async def create(self, db: AsyncSession, obj: CreateFoodTagParam) -> None:
        """
        创建食物标签

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateFoodTagParam) -> int:
        """
        更新食物标签

        :param db: 数据库会话
        :param pk: 标签 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除食物标签

        :param db: 数据库会话
        :param pk: 标签 ID
        :return:
        """
        return await self.delete_model_by_column(db, id=pk, logical_deletion=True, deleted_flag_column='del_flag')

    async def get_food_tags(self, db: AsyncSession, food_id: int) -> Sequence[FoodTag]:
        """
        获取食物的所有标签

        :param db: 数据库会话
        :param food_id: 食物 ID
        :return:
        """
        stmt = (
            select(FoodTag)
            .join(FoodTagRelation, FoodTag.id == FoodTagRelation.tag_id)
            .where(FoodTagRelation.food_id == food_id, FoodTag.del_flag == False)  # noqa: E712
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def add_food_tags(self, db: AsyncSession, food_id: int, tag_ids: list[int]) -> None:
        """
        为食物添加标签

        :param db: 数据库会话
        :param food_id: 食物 ID
        :param tag_ids: 标签 ID 列表
        :return:
        """
        values = [{'food_id': food_id, 'tag_id': tag_id} for tag_id in tag_ids]
        stmt = insert(FoodTagRelation).values(values)
        await db.execute(stmt)

    async def remove_food_tags(self, db: AsyncSession, food_id: int, tag_ids: list[int]) -> None:
        """
        移除食物的标签

        :param db: 数据库会话
        :param food_id: 食物 ID
        :param tag_ids: 标签 ID 列表
        :return:
        """
        stmt = delete(FoodTagRelation).where(
            FoodTagRelation.food_id == food_id, FoodTagRelation.tag_id.in_(tag_ids)
        )
        await db.execute(stmt)


food_tag_dao: CRUDFoodTag = CRUDFoodTag(FoodTag)
