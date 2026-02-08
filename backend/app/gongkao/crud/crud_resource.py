#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资料 CRUD"""
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model.resource import GkResource
from backend.app.gongkao.schema.resource import CreateResourceParam, UpdateResourceParam


class CRUDResource(CRUDPlus[GkResource]):
    """资料 CRUD"""

    async def get(self, db: AsyncSession, pk: int) -> GkResource | None:
        """获取资料详情"""
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
        """获取资料列表"""
        filters = {}
        # 如果是整数，则加入精确匹配 filters；如果是列表，稍后手动处理
        if category_id is not None and isinstance(category_id, int):
            filters['category_id'] = category_id
        if file_type is not None:
            filters['file_type'] = file_type
        if status is not None:
            filters['status'] = status

        stmt = await self.select_order(
            'sort_order',
            'desc',
            **filters
        )

        if category_id is not None and isinstance(category_id, list):
            stmt = stmt.where(GkResource.category_id.in_(category_id))

        if title:
            stmt = stmt.where(GkResource.title.contains(title))

        return stmt

    async def create(self, db: AsyncSession, obj_in: CreateResourceParam) -> GkResource:
        """创建资料"""
        return await self.create_model(db, obj_in, commit=True)

    async def update(self, db: AsyncSession, pk: int, obj_in: UpdateResourceParam) -> int:
        """更新资料"""
        return await self.update_model(db, pk, obj_in, commit=True)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """删除资料"""
        return await self.delete_model(db, pk, commit=True)

    async def increment_view(self, db: AsyncSession, pk: int) -> int:
        """增加查看次数"""
        resource = await self.get(db, pk)
        if resource:
            resource.view_count += 1
            await db.commit()
            return resource.view_count
        return 0


resource_dao: CRUDResource = CRUDResource(GkResource)
