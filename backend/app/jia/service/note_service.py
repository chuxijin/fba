#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.crud.crud_note import note_dao
from backend.app.jia.model.note import Note
from backend.app.jia.schema.note import CreateNoteParam, UpdateNoteParam
from backend.common.exception import errors


class NoteService:
    """笔记服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Note:
        """
        获取笔记详情

        :param db: 数据库会话
        :param pk: 笔记 ID
        :return:
        """
        note = await note_dao.get(db, pk)
        if not note:
            raise errors.NotFoundError(msg='笔记不存在')
        return note

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        type: str | None = None,
        parent_id: int | None = None,
        name: str | None = None,
        is_pinned: int | None = None,
        is_favorite: int | None = None,
        sync_status: str | None = None,
    ) -> list[Note]:
        """
        获取笔记列表

        :param db: 数据库会话
        :param type: 类型
        :param parent_id: 父级 ID
        :param name: 名称
        :param is_pinned: 是否置顶
        :param is_favorite: 是否收藏
        :param sync_status: 同步状态
        :return:
        """
        select_stmt = await note_dao.get_select(type, parent_id, name, is_pinned, is_favorite, sync_status)
        notes = await db.execute(select_stmt)
        return list(notes.scalars().all())

    @staticmethod
    async def get_children(*, db: AsyncSession, parent_id: int) -> list[Note]:
        """
        获取子笔记/文件夹列表

        :param db: 数据库会话
        :param parent_id: 父级 ID
        :return:
        """
        return list(await note_dao.get_children(db, parent_id))

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateNoteParam, user_id: int) -> None:
        """
        创建笔记

        :param db: 数据库会话
        :param obj: 创建笔记参数
        :param user_id: 用户 ID
        :return:
        """
        if obj.parent_id:
            parent = await note_dao.get(db, obj.parent_id)
            if not parent:
                raise errors.NotFoundError(msg='父级不存在')
            if parent.type != 'folder':
                raise errors.ForbiddenError(msg='父级必须是文件夹类型')
        await note_dao.create(db, obj, user_id)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateNoteParam, user_id: int) -> int:
        """
        更新笔记

        :param db: 数据库会话
        :param pk: 笔记 ID
        :param obj: 更新笔记参数
        :param user_id: 用户 ID
        :return:
        """
        note = await note_dao.get(db, pk)
        if not note:
            raise errors.NotFoundError(msg='笔记不存在')
        if obj.parent_id is not None:
            if obj.parent_id == pk:
                raise errors.ForbiddenError(msg='禁止关联自身为父级')
            if obj.parent_id > 0:
                parent = await note_dao.get(db, obj.parent_id)
                if not parent:
                    raise errors.NotFoundError(msg='父级不存在')
                if parent.type != 'folder':
                    raise errors.ForbiddenError(msg='父级必须是文件夹类型')
        count = await note_dao.update(db, pk, obj, user_id)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pks: list[int]) -> int:
        """
        批量删除笔记

        :param db: 数据库会话
        :param pks: 笔记 ID 列表
        :return:
        """
        count = await note_dao.delete(db, pks)
        return count


note_service: NoteService = NoteService()

