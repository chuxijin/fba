#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import QuestionChapter
from backend.app.question_bank.schema.chapter import CreateChapterParam, UpdateChapterParam


class CRUDChapter(CRUDPlus[QuestionChapter]):
    """章节数据库操作类"""

    async def get(self, db: AsyncSession, chapter_id: int) -> QuestionChapter | None:
        """
        获取章节详情

        :param db: 数据库会话
        :param chapter_id: 章节 ID
        :return:
        """
        return await self.select_model_by_column(db, id=chapter_id)

    async def get_by_bank(
        self,
        db: AsyncSession,
        bank_id: int,
    ) -> Sequence[QuestionChapter]:
        """
        获取题库所有章节

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :return:
        """
        return await self.select_models_order(db, 'sort_order', 'asc', bank_id=bank_id)

    async def get_children(self, db: AsyncSession, parent_id: int) -> Sequence[QuestionChapter]:
        """
        获取子章节列表

        :param db: 数据库会话
        :param parent_id: 父级章节 ID
        :return:
        """
        return await self.select_models(db, parent_id=parent_id)

    async def get_by_name(
        self,
        db: AsyncSession,
        bank_id: int,
        name: str,
        parent_id: int | None = None,
    ) -> QuestionChapter | None:
        """
        根据名称获取章节

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param name: 章节名称
        :param parent_id: 父级章节 ID（None 表示一级章节）
        :return:
        """
        return await self.select_model_by_column(db, bank_id=bank_id, name=name, parent_id=parent_id)

    async def create(self, db: AsyncSession, obj: CreateChapterParam) -> None:
        """
        创建章节

        :param db: 数据库会话
        :param obj: 创建章节参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, chapter_id: int, obj: UpdateChapterParam) -> int:
        """
        更新章节

        :param db: 数据库会话
        :param chapter_id: 章节 ID
        :param obj: 更新章节参数
        :return:
        """
        return await self.update_model(db, chapter_id, obj)

    async def delete(self, db: AsyncSession, chapter_ids: list[int]) -> int:
        """
        批量删除章节

        :param db: 数据库会话
        :param chapter_ids: 章节 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=chapter_ids)


chapter_dao: CRUDChapter = CRUDChapter(QuestionChapter)
