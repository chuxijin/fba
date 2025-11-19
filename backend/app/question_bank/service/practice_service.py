#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
刷题服务类

设计原则：
- 专门为客户端刷题场景提供简化的服务接口
- 不重复实现业务逻辑，而是调用 question_service
- 提供符合刷题流程的便捷方法
"""
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_question import question_dao
from backend.app.question_bank.model import Question, QuestionAnalysis
from backend.app.question_bank.service.question_service import question_service
from backend.common.exception import errors


class PracticeService:
    """刷题服务类"""

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
        questions = await question_dao.get_all(
            db=db,
            bank_id=bank_id,
            chapter_id=chapter_id,
            type=type,
            difficulty=difficulty,
            is_active=True,  # 只返回启用的题目
            review_status=10,  # 只返回已审核通过的题目
        )
        return questions

    @staticmethod
    async def get_question_for_practice(*, db: AsyncSession, question_id: int) -> Question:
        """
        获取题目详情用于练习（不含答案）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        question = await question_dao.get_with_relations(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')
        if not question.is_active:
            raise errors.NotFoundError(msg='题目已禁用')
        if question.review_status != 10:
            raise errors.NotFoundError(msg='题目未通过审核')
        return question

    @staticmethod
    async def get_practice_analysis(*, db: AsyncSession, question_id: int) -> QuestionAnalysis:
        """
        查看题目解析（刷题后查看答案）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        # 调用 question_service 的获取解析方法，并增加查看次数
        analysis = await question_service.get_analysis(db=db, question_id=question_id, increment_view=True)
        return analysis


practice_service: PracticeService = PracticeService()
