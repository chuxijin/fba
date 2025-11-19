#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.jia.model.note import Note
from backend.app.jia.schema.note import CreateNoteParam, UpdateNoteParam


class CRUDNote(CRUDPlus[Note]):
    """笔记数据库操作类"""

    async def get(self, db: AsyncSession, note_id: int) -> Note | None:
        """
        获取笔记详情

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :return:
        """
        return await self.select_model_by_column(db, id=note_id, deleted_at=None)

    async def get_by_server_id(self, db: AsyncSession, server_id: str) -> Note | None:
        """
        通过服务器 ID 获取笔记

        :param db: 数据库会话
        :param server_id: 服务器 ID
        :return:
        """
        return await self.select_model_by_column(db, server_id=server_id, deleted_at=None)

    async def get_select(
        self,
        type: str | None,
        parent_id: int | None,
        name: str | None,
        is_pinned: int | None,
        is_favorite: int | None,
        sync_status: str | None,
    ) -> Select:
        """
        获取笔记列表查询表达式

        :param type: 类型
        :param parent_id: 父级 ID
        :param name: 名称
        :param is_pinned: 是否置顶
        :param is_favorite: 是否收藏
        :param sync_status: 同步状态
        :return:
        """
        filters = {'deleted_at': None}

        if type is not None:
            filters['type'] = type
        if parent_id is not None:
            filters['parent_id'] = parent_id
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if is_pinned is not None:
            filters['is_pinned'] = is_pinned
        if is_favorite is not None:
            filters['is_favorite'] = is_favorite
        if sync_status is not None:
            filters['sync_status'] = sync_status

        return await self.select_order('sort_order', 'asc', **filters)

    async def get_children(self, db: AsyncSession, parent_id: int) -> Sequence[Note]:
        """
        获取子笔记/文件夹列表

        :param db: 数据库会话
        :param parent_id: 父级 ID
        :return:
        """
        return await self.select_models_order(db, 'sort_order', 'asc', parent_id=parent_id, deleted_at=None)

    async def create(self, db: AsyncSession, obj: CreateNoteParam, user_id: int) -> Note:
        """
        创建笔记

        :param db: 数据库会话
        :param obj: 创建笔记参数
        :param user_id: 用户 ID
        :return:
        """
        dict_obj = obj.model_dump()
        dict_obj['created_by'] = user_id
        return await self.create_model(db, dict_obj, commit=False)

    async def update(self, db: AsyncSession, note_id: int, obj: UpdateNoteParam, user_id: int) -> int:
        """
        更新笔记

        :param db: 数据库会话
        :param note_id: 笔记 ID
        :param obj: 更新笔记参数
        :param user_id: 用户 ID
        :return:
        """
        dict_obj = obj.model_dump(exclude_unset=True)
        dict_obj['updated_by'] = user_id
        return await self.update_model(db, note_id, dict_obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        批量软删除笔记

        :param db: 数据库会话
        :param pks: 笔记 ID 列表
        :return:
        """
        import time
        deleted_at = int(time.time())
        count = 0
        for pk in pks:
            count += await self.update_model_by_column(db, {'deleted_at': deleted_at}, id=pk)
        return count


note_dao: CRUDNote = CRUDNote(Note)

