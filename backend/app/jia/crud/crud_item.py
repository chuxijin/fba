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
        ids: list[int] | None = None,
        name: str | None = None,
        category: str | None = None,
        status: str | None = None,
        location: str | None = None,
    ) -> Select:
        """
        获取物品列表查询表达式

        :param user_id: 用户 ID
        :param ids: 物品 ID 列表
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

        stmt = await self.select_order('updated_time', 'desc', **filters)

        # 单独处理 ids 过滤（CRUDPlus 不支持 in_ 语法）
        if ids is not None:
            stmt = stmt.where(JiaItem.id.in_(ids))

        return stmt

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

    async def create(self, db: AsyncSession, obj: CreateItemParam, user_id: int, vector: list[float] | None = None) -> JiaItem:
        """
        创建物品

        :param db: 数据库会话
        :param obj: 创建物品参数
        :param user_id: 用户 ID
        :param vector: 物品向量
        :return:
        """
        data = obj.model_dump()
        if vector:
            data['vector'] = vector

        item = JiaItem(
            **data,
            created_by=user_id,
        )
        # 计算初始状态
        item.status = item.calculate_status()
        db.add(item)
        await db.flush()
        return item

    async def update(self, db: AsyncSession, pk: int, obj: UpdateItemParam, user_id: int, vector: list[float] | None = None) -> int:
        """
        更新物品

        :param db: 数据库会话
        :param pk: 物品 ID
        :param obj: 更新物品参数
        :param user_id: 用户 ID
        :param vector: 物品向量
        :return:
        """
        update_data = obj.model_dump(exclude_unset=True)
        update_data['updated_by'] = user_id
        if vector:
            update_data['vector'] = vector
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

    async def delete_items(self, db: AsyncSession, pks: list[int], user_id: int) -> tuple[int, list[str | None]]:
        """
        删除物品（支持单个和批量）

        :param db: 数据库会话
        :param pks: 物品 ID 列表
        :param user_id: 用户 ID
        :return: (删除数量, 图片路径列表)
        """
        from sqlalchemy import select, delete

        # 先查询要删除的物品的图片路径
        stmt = select(JiaItem.image_path).where(
            JiaItem.id.in_(pks),
            JiaItem.created_by == user_id,
        )
        result = await db.execute(stmt)
        image_paths = [row[0] for row in result.all()]

        # 执行删除
        delete_stmt = delete(JiaItem).where(
            JiaItem.id.in_(pks),
            JiaItem.created_by == user_id,
        )
        result = await db.execute(delete_stmt)
        return result.rowcount, image_paths


    async def search_by_vector(self, db: AsyncSession, vector: list[float], user_id: int, limit: int = 5):
        """
        根据向量搜索相似物品
        """
        from sqlalchemy import select
        
        # 使用 pgvector 的 L2 距离操作符 <->
        stmt = select(JiaItem).where(
            JiaItem.created_by == user_id
        ).order_by(JiaItem.vector.l2_distance(vector)).limit(limit)
        
        result = await db.execute(stmt)
        return result.scalars().all()


item_dao = CRUDItem(JiaItem)
