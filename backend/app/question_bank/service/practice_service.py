#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_question import question_dao
from backend.app.question_bank.model import Question, QuestionAnalysis
from backend.app.question_bank.service.question_service import question_service
from backend.common.exception import errors


class PracticeService:
    """刷题服务类（只读）"""

    @staticmethod
    async def get_practice_questions(
        *,
        db: AsyncSession,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        type: str | None = None,
        difficulty: str | None = None,
    ) -> Sequence[Question]:
        """
        获取可练习的题目列表（不含答案）

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param type: 题型
        :param difficulty: 难度
        :return:
        """
        return await question_dao.get_all(
            db=db,
            bank_id=bank_id,
            chapter_id=chapter_id,
            type=type,
            difficulty=difficulty,
            is_active=True,
            review_status=10,
        )

    @staticmethod
    async def get_question_for_practice(*, db: AsyncSession, question_id: int) -> dict[str, Any]:
        """
        获取题目详情用于练习（返回标准化 DTO，不含答案）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        question = await question_dao.get_with_relations(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')
        if question.content_status != 10:
            raise errors.NotFoundError(msg='题目内容未通过审核')

        return question_service.serialize_question(
            question=question,
            include_analysis=False,
            include_materials=False,
        )

    @staticmethod
    async def get_practice_analysis(*, db: AsyncSession, question_id: int) -> QuestionAnalysis:
        """
        查看题目解析（刷题后查看答案）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        return await question_service.get_analysis(db=db, question_id=question_id, increment_view=True)


practice_service: PracticeService = PracticeService()
