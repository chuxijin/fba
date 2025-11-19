#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.jia.model.tag import Tag
from backend.app.jia.schema.tag import CreateTagParam, UpdateTagParam


class CRUDTag(CRUDPlus[Tag]):
    """标签数据库操作类"""

    async def get(self, db: AsyncSession, tag_id: int) -> Tag | None:
        """
        获取标签详情

        :param db: 数据库会话
        :param tag_id: 标签 ID
        :return:
        """
        return await self.select_model_by_column(db, id=tag_id, deleted_at=None)

    async def get_by_name(self, db: AsyncSession, name: str, user_id: int) -> Tag | None:
        """
        通过名称获取标签

        :param db: 数据库会话
        :param name: 标签名称
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_model_by_column(db, name=name, created_by=user_id, deleted_at=None)

    async def get_by_server_id(self, db: AsyncSession, server_id: str) -> Tag | None:
        """
        通过服务器 ID 获取标签

        :param db: 数据库会话
        :param server_id: 服务器 ID
        :return:
        """
        return await self.select_model_by_column(db, server_id=server_id, deleted_at=None)

    async def get_select(
        self,
        name: str | None,
        sync_status: str | None,
    ) -> Select:
        """
        获取标签列表查询表达式

        :param name: 标签名称
        :param sync_status: 同步状态
        :return:
        """
        filters = {'deleted_at': None}

        if name is not None:
            filters['name__like'] = f'%{name}%'
        if sync_status is not None:
            filters['sync_status'] = sync_status

        return await self.select_order('created_time', 'desc', **filters)

    async def get_all(self, db: AsyncSession, user_id: int) -> Sequence[Tag]:
        """
        获取所有标签

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_models_order(db, 'created_time', 'desc', created_by=user_id, deleted_at=None)

    async def create(self, db: AsyncSession, obj: CreateTagParam, user_id: int) -> Tag:
        """
        创建标签

        :param db: 数据库会话
        :param obj: 创建标签参数
        :param user_id: 用户 ID
        :return:
        """
        dict_obj = obj.model_dump()
        dict_obj['created_by'] = user_id
        return await self.create_model(db, dict_obj, commit=False)

    async def update(self, db: AsyncSession, tag_id: int, obj: UpdateTagParam, user_id: int) -> int:
        """
        更新标签

        :param db: 数据库会话
        :param tag_id: 标签 ID
        :param obj: 更新标签参数
        :param user_id: 用户 ID
        :return:
        """
        dict_obj = obj.model_dump(exclude_unset=True)
        dict_obj['updated_by'] = user_id
        return await self.update_model(db, tag_id, dict_obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        批量软删除标签

        :param db: 数据库会话
        :param pks: 标签 ID 列表
        :return:
        """
        import time
        deleted_at = int(time.time())
        count = 0
        for pk in pks:
            count += await self.update_model_by_column(db, {'deleted_at': deleted_at}, id=pk)
        return count


tag_dao: CRUDTag = CRUDTag(Tag)

