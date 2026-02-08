#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.crud import item_dao
from backend.app.jia.model import JiaItem
from backend.app.jia.schema import CreateItemParam, UpdateItemParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class ItemService:
    """物品服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int, user_id: int) -> JiaItem:
        """
        获取物品

        :param db: 数据库会话
        :param pk: 物品 ID
        :param user_id: 用户 ID
        :return:
        """
        item = await item_dao.get_by_user(db, user_id, pk)
        if not item:
            raise errors.NotFoundError(msg='物品不存在')
        return item

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        user_id: int,
        name: str | None = None,
        category: str | None = None,
        status: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        """
        获取物品列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param name: 名称
        :param category: 分类
        :param status: 状态
        :param location: 存放位置
        :return:
        """
        select_stmt = await item_dao.get_list(
            user_id=user_id,
            name=name,
            category=category,
            status=status,
            location=location,
        )
        return await paging_data(db, select_stmt)

    @staticmethod
    async def get_categories(*, db: AsyncSession, user_id: int) -> list[str]:
        """
        获取用户的所有分类

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await item_dao.get_categories(db, user_id)

    @staticmethod
    async def get_status_stats(*, db: AsyncSession, user_id: int) -> dict[str, int]:
        """
        获取物品状态统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        from sqlalchemy import select, func

        stmt = (
            select(JiaItem.status, func.count(JiaItem.id))
            .where(JiaItem.created_by == user_id)
            .group_by(JiaItem.status)
        )
        result = await db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateItemParam, user_id: int) -> JiaItem:
        """
        创建物品

        :param db: 数据库会话
        :param obj: 创建物品参数
        :param user_id: 用户 ID
        :return:
        """
        return await item_dao.create(db, obj, user_id)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateItemParam, user_id: int) -> int:
        """
        更新物品

        :param db: 数据库会话
        :param pk: 物品 ID
        :param obj: 更新物品参数
        :param user_id: 用户 ID
        :return:
        """
        item = await item_dao.get_by_user(db, user_id, pk)
        if not item:
            raise errors.NotFoundError(msg='物品不存在')
        return await item_dao.update(db, pk, obj, user_id)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int, user_id: int) -> int:
        """
        删除物品

        :param db: 数据库会话
        :param pk: 物品 ID
        :param user_id: 用户 ID
        :return:
        """
        item = await item_dao.get_by_user(db, user_id, pk)
        if not item:
            raise errors.NotFoundError(msg='物品不存在')
        return await item_dao.delete(db, pk)

    @staticmethod
    async def batch_delete(*, db: AsyncSession, pks: list[int], user_id: int) -> int:
        """
        批量删除物品

        :param db: 数据库会话
        :param pks: 物品 ID 列表
        :param user_id: 用户 ID
        :return:
        """
        return await item_dao.batch_delete(db, pks, user_id)


item_service = ItemService()
