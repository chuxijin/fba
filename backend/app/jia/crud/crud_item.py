#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy_crud_plus import CRUDPlus

from backend.app.jia.model import JiaItem
from backend.app.jia.schema import CreateItemParam, UpdateItemParam


class CRUDItem(CRUDPlus[JiaItem]):
    """物品数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> JiaItem | None:
        """
        获取物品

        :param db: 数据库会话
        :param pk: 物品 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_user(self, db: AsyncSession, user_id: int, pk: int) -> JiaItem | None:
        """
        获取用户的物品

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param pk: 物品 ID
        :return:
        """
        return await self.select_model(db, pk, created_by=user_id)

    async def get_list(
        self,
        *,
        user_id: int,
        name: str | None = None,
        category: str | None = None,
        status: str | None = None,
        location: str | None = None,
    ) -> Select:
        """
        获取物品列表查询表达式

        :param user_id: 用户 ID
        :param name: 名称
        :param category: 分类
        :param status: 状态
        :param location: 存放位置
        :return:
        """
        filters = {'created_by': user_id}
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if category is not None:
            filters['category'] = category
        if status is not None:
            filters['status'] = status
        if location is not None:
            filters['location__like'] = f'%{location}%'
        return await self.select_order('updated_time', 'desc', **filters)

    async def get_categories(self, db: AsyncSession, user_id: int) -> list[str]:
        """
        获取用户的所有分类

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        from sqlalchemy import select, distinct

        stmt = select(distinct(JiaItem.category)).where(
            JiaItem.created_by == user_id,
            JiaItem.category.isnot(None),
        )
        result = await db.execute(stmt)
        return [row[0] for row in result.all()]

    async def create(self, db: AsyncSession, obj: CreateItemParam, user_id: int) -> JiaItem:
        """
        创建物品

        :param db: 数据库会话
        :param obj: 创建物品参数
        :param user_id: 用户 ID
        :return:
        """
        item = JiaItem(
            **obj.model_dump(),
            created_by=user_id,
        )
        # 计算初始状态
        item.status = item.calculate_status()
        db.add(item)
        await db.flush()
        return item

    async def update(self, db: AsyncSession, pk: int, obj: UpdateItemParam, user_id: int) -> int:
        """
        更新物品

        :param db: 数据库会话
        :param pk: 物品 ID
        :param obj: 更新物品参数
        :param user_id: 用户 ID
        :return:
        """
        update_data = obj.model_dump(exclude_unset=True)
        update_data['updated_by'] = user_id
        count = await self.update_model(db, pk, update_data)

        # 更新后重新计算状态
        if count > 0:
            item = await self.get(db, pk)
            if item:
                item.update_status()

        return count

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除物品

        :param db: 数据库会话
        :param pk: 物品 ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def batch_delete(self, db: AsyncSession, pks: list[int], user_id: int) -> int:
        """
        批量删除物品

        :param db: 数据库会话
        :param pks: 物品 ID 列表
        :param user_id: 用户 ID
        :return:
        """
        from sqlalchemy import delete

        stmt = delete(JiaItem).where(
            JiaItem.id.in_(pks),
            JiaItem.created_by == user_id,
        )
        result = await db.execute(stmt)
        return result.rowcount


item_dao = CRUDItem(JiaItem)
