#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资料服务"""
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_resource import resource_dao
from backend.app.gongkao.model.resource import GkResource
from backend.app.gongkao.schema.resource import CreateResourceParam, UpdateResourceParam


class ResourceService:
    """资料服务"""

    @staticmethod
    async def get(db: AsyncSession, pk: int) -> GkResource | None:
        """获取资料详情"""
        return await resource_dao.get(db, pk)

    @staticmethod
    async def get_list(
        db: AsyncSession,
        *,
        title: str | None = None,
        category: str | None = None,
        file_type: str | None = None,
        status: bool | None = None,
    ) -> Select:
        """获取资料列表"""
        return await resource_dao.get_list(
            db,
            title=title,
            category=category,
            file_type=file_type,
            status=status,
        )

    @staticmethod
    async def create(db: AsyncSession, obj_in: CreateResourceParam) -> GkResource:
        """创建资料"""
        return await resource_dao.create(db, obj_in)

    @staticmethod
    async def update(db: AsyncSession, pk: int, obj_in: UpdateResourceParam) -> int:
        """更新资料"""
        return await resource_dao.update(db, pk, obj_in)

    @staticmethod
    async def delete(db: AsyncSession, pk: int) -> int:
        """删除资料"""
        return await resource_dao.delete(db, pk)

    @staticmethod
    async def increment_view(db: AsyncSession, pk: int) -> int:
        """增加查看次数"""
        return await resource_dao.increment_view(db, pk)


resource_service: ResourceService = ResourceService()
