#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.jia.model.categories import JiaCategory
from backend.app.jia.schema.category import CreateCategoryParam, UpdateCategoryParam


class CRUDCategory(CRUDPlus[JiaCategory]):
    """分类数据库操作类"""

    async def get(self, db: AsyncSession, category_id: int) -> JiaCategory | None:
        """
        获取分类详情

        :param db: 数据库会话
        :param category_id: 分类 ID
        :return:
        """
        return await self.select_model_by_column(db, id=category_id, deleted_at=None)

    async def get_by_name(self, db: AsyncSession, name: str, user_id: int) -> JiaCategory | None:
        """
        通过名称获取分类

        :param db: 数据库会话
        :param name: 分类名称
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_model_by_column(db, name=name, created_by=user_id, deleted_at=None)

    async def get_by_server_id(self, db: AsyncSession, server_id: str) -> JiaCategory | None:
        """
        通过服务器 ID 获取分类

        :param db: 数据库会话
        :param server_id: 服务器 ID
        :return:
        """
        return await self.select_model_by_column(db, server_id=server_id, deleted_at=None)

    async def get_select(
        self,
        parent_id: int | None,
        name: str | None,
        sync_status: str | None,
    ) -> Select:
        """
        获取分类列表查询表达式

        :param parent_id: 父级分类 ID
        :param name: 分类名称
        :param sync_status: 同步状态
        :return:
        """
        filters = {'deleted_at': None}

        if parent_id is not None:
            filters['parent_id'] = parent_id
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if sync_status is not None:
            filters['sync_status'] = sync_status

        return await self.select_order('sort_order', 'asc', **filters)

    async def get_children(self, db: AsyncSession, parent_id: int) -> Sequence[JiaCategory]:
        """
        获取子分类列表

        :param db: 数据库会话
        :param parent_id: 父级分类 ID
        :return:
        """
        return await self.select_models_order(db, 'sort_order', 'asc', parent_id=parent_id, deleted_at=None)

    async def get_all(self, db: AsyncSession, user_id: int) -> Sequence[JiaCategory]:
        """
        获取所有分类

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_models_order(db, 'sort_order', 'asc', created_by=user_id, deleted_at=None)

    async def create(self, db: AsyncSession, obj: CreateCategoryParam, user_id: int) -> JiaCategory:
        """
        创建分类

        :param db: 数据库会话
        :param obj: 创建分类参数
        :param user_id: 用户 ID
        :return:
        """
        dict_obj = obj.model_dump()
        dict_obj['created_by'] = user_id
        return await self.create_model(db, dict_obj, commit=False)

    async def update(self, db: AsyncSession, category_id: int, obj: UpdateCategoryParam, user_id: int) -> int:
        """
        更新分类

        :param db: 数据库会话
        :param category_id: 分类 ID
        :param obj: 更新分类参数
        :param user_id: 用户 ID
        :return:
        """
        dict_obj = obj.model_dump(exclude_unset=True)
        dict_obj['updated_by'] = user_id
        return await self.update_model(db, category_id, dict_obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        批量软删除分类

        :param db: 数据库会话
        :param pks: 分类 ID 列表
        :return:
        """
        import time
        deleted_at = int(time.time())
        count = 0
        for pk in pks:
            count += await self.update_model_by_column(db, {'deleted_at': deleted_at}, id=pk)
        return count


category_dao: CRUDCategory = CRUDCategory(JiaCategory)

