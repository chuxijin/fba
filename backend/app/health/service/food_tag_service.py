#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.health.crud.crud_food import food_dao
from backend.app.health.crud.crud_food_tag import food_tag_dao
from backend.app.health.model import FoodTag
from backend.app.health.schema.food_tag import (
    AddFoodTagRelationParam,
    CreateFoodTagParam,
    RemoveFoodTagRelationParam,
    UpdateFoodTagParam,
)
from backend.common.exception import errors


class FoodTagService:
    """食物标签服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> FoodTag:
        """
        获取食物标签详情

        :param db: 数据库会话
        :param pk: 标签 ID
        :return:
        """
        tag = await food_tag_dao.get(db, pk)
        if not tag:
            raise errors.NotFoundError(msg='食物标签不存在')
        return tag

    @staticmethod
    async def get_select(*, name: str | None, tag_group: int | None, status: int | None) -> Select:
        """
        获取食物标签列表查询表达式

        :param name: 标签名称
        :param tag_group: 标签分组
        :param status: 状态
        :return:
        """
        return await food_tag_dao.get_select(name, tag_group, status)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateFoodTagParam) -> None:
        """
        创建食物标签

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        tag = await food_tag_dao.get_by_name(db, obj.name)
        if tag:
            raise errors.ConflictError(msg='标签名称已存在')
        await food_tag_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateFoodTagParam) -> int:
        """
        更新食物标签

        :param db: 数据库会话
        :param pk: 标签 ID
        :param obj: 更新参数
        :return:
        """
        tag = await food_tag_dao.get(db, pk)
        if not tag:
            raise errors.NotFoundError(msg='食物标签不存在')
        if tag.name != obj.name and await food_tag_dao.get_by_name(db, obj.name):
            raise errors.ConflictError(msg='标签名称已存在')
        count = await food_tag_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除食物标签

        :param db: 数据库会话
        :param pk: 标签 ID
        :return:
        """
        tag = await food_tag_dao.get(db, pk)
        if not tag:
            raise errors.NotFoundError(msg='食物标签不存在')
        count = await food_tag_dao.delete(db, pk)
        return count

    @staticmethod
    async def get_food_tags(*, db: AsyncSession, food_id: int) -> Sequence[FoodTag]:
        """
        获取食物的所有标签

        :param db: 数据库会话
        :param food_id: 食物 ID
        :return:
        """
        food = await food_dao.get(db, food_id)
        if not food:
            raise errors.NotFoundError(msg='食物不存在')
        return await food_tag_dao.get_food_tags(db, food_id)

    @staticmethod
    async def add_food_tags(*, db: AsyncSession, obj: AddFoodTagRelationParam) -> None:
        """
        为食物添加标签

        :param db: 数据库会话
        :param obj: 添加参数
        :return:
        """
        food = await food_dao.get(db, obj.food_id)
        if not food:
            raise errors.NotFoundError(msg='食物不存在')
        for tag_id in obj.tag_ids:
            tag = await food_tag_dao.get(db, tag_id)
            if not tag:
                raise errors.NotFoundError(msg=f'标签 ID {tag_id} 不存在')
        await food_tag_dao.add_food_tags(db, obj.food_id, obj.tag_ids)

    @staticmethod
    async def remove_food_tags(*, db: AsyncSession, obj: RemoveFoodTagRelationParam) -> None:
        """
        移除食物的标签

        :param db: 数据库会话
        :param obj: 移除参数
        :return:
        """
        food = await food_dao.get(db, obj.food_id)
        if not food:
            raise errors.NotFoundError(msg='食物不存在')
        await food_tag_dao.remove_food_tags(db, obj.food_id, obj.tag_ids)


food_tag_service: FoodTagService = FoodTagService()
