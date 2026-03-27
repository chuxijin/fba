#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model.resource import GkResource
from backend.app.gongkao.schema.resource import CreateResourceParam, UpdateResourceParam


class CRUDResource(CRUDPlus[GkResource]):
    """资料数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkResource | None:
        """
        获取资料详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_list(
        self,
        db: AsyncSession,
        *,
        title: str | None = None,
        category_id: int | list[int] | None = None,
        file_type: str | None = None,
        status: bool | None = None,
    ) -> Select:
        """
        获取资料列表查询表达式

        :param db: 数据库会话
        :param title: 标题关键字
        :param category_id: 分类 ID（支持列表）
        :param file_type: 文件类型
        :param status: 状态
        :return:
        """
        filters = {}
        if category_id is not None and isinstance(category_id, int):
            filters['category_id'] = category_id
        if file_type is not None:
            filters['file_type'] = file_type
        if status is not None:
            filters['status'] = status

        stmt = await self.select_order('sort_order', 'desc', **filters)

        if category_id is not None and isinstance(category_id, list):
            stmt = stmt.where(GkResource.category_id.in_(category_id))

        if title:
            stmt = stmt.where(GkResource.title.contains(title))

        return stmt

    async def create(self, db: AsyncSession, obj_in: CreateResourceParam) -> GkResource:
        """
        创建资料

        :param db: 数据库会话
        :param obj_in: 创建参数
        :return:
        """
        resource = await self.create_model(db, obj_in)
        await db.flush()
        await db.refresh(resource)
        return resource

    async def update(self, db: AsyncSession, pk: int, obj_in: UpdateResourceParam) -> int:
        """
        更新资料

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj_in: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj_in)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除资料

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def increment_view(self, db: AsyncSession, pk: int) -> int:
        """
        增加查看次数

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        resource = await self.get(db, pk)
        if resource:
            return await self.update_model(db, pk, {'view_count': resource.view_count + 1})
        return 0


resource_dao: CRUDResource = CRUDResource(GkResource)
