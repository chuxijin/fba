#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.model import QuestionChapter
from backend.app.question_bank.schema.chapter import CreateChapterParam, DeleteChapterParam, UpdateChapterParam
from backend.common.exception import errors
from backend.utils.build_tree import get_tree_data


class ChapterService:
    """章节服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> QuestionChapter:
        """
        获取章节详情

        :param db: 数据库会话
        :param pk: 章节 ID
        :return:
        """
        chapter = await chapter_dao.get(db, pk)
        if not chapter:
            raise errors.NotFoundError(msg='章节不存在')
        return chapter

    @staticmethod
    async def get_tree(
        *,
        db: AsyncSession,
        bank_id: int,
    ) -> list[dict[str, Any]]:
        """
        获取章节树形结构

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :return:
        """
        chapter_select = await chapter_dao.get_by_bank(db, bank_id)
        tree_data = get_tree_data(chapter_select, sort_key='sort_order')
        return tree_data

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateChapterParam) -> None:
        """
        创建章节

        :param db: 数据库会话
        :param obj: 创建章节参数
        :return:
        """
        bank = await bank_dao.get(db, obj.bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')
        if obj.parent_id:
            parent_chapter = await chapter_dao.get(db, obj.parent_id)
            if not parent_chapter:
                raise errors.NotFoundError(msg='父级章节不存在')
        await chapter_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateChapterParam) -> int:
        """
        更新章节

        :param db: 数据库会话
        :param pk: 章节 ID
        :param obj: 更新章节参数
        :return:
        """
        chapter = await chapter_dao.get(db, pk)
        if not chapter:
            raise errors.NotFoundError(msg='章节不存在')
        bank = await bank_dao.get(db, obj.bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')
        if obj.parent_id:
            parent_chapter = await chapter_dao.get(db, obj.parent_id)
            if not parent_chapter:
                raise errors.NotFoundError(msg='父级章节不存在')
        if obj.parent_id == chapter.id:
            raise errors.ForbiddenError(msg='禁止关联自身为父级')
        count = await chapter_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteChapterParam) -> int:
        """
        删除章节

        :param db: 数据库会话
        :param obj: 删除章节参数
        :return:
        """
        for chapter_id in obj.ids:
            children = await chapter_dao.get_children(db, chapter_id)
            if children:
                raise errors.ConflictError(msg='章节下存在子章节，无法删除')
        count = await chapter_dao.delete(db, obj.ids)
        return count


chapter_service: ChapterService = ChapterService()
