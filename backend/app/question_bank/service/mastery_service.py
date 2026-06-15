#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_mastery import mastery_dao
from backend.app.question_bank.model.mastery import WrongMasteryStatus
from backend.app.question_bank.schema.mastery import (
    GetForgottenItem,
    GetMasteryStatsResponse,
)


class MasteryService:
    """错题掌握状态服务"""

    @staticmethod
    async def on_correct(
        *,
        db: AsyncSession,
        user_id: int,
        question_id: int | None = None,
        custom_question_id: int | None = None,
        mastery_threshold: int = 3,
    ) -> WrongMasteryStatus:
        """
        做题答对时更新掌握状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题库题目 ID
        :param custom_question_id: 自定义错题 ID
        :param mastery_threshold: 掌握阈值
        :return:
        """
        return await mastery_dao.on_correct(
            db, user_id, question_id, custom_question_id, mastery_threshold,
        )

    @staticmethod
    async def on_wrong(
        *,
        db: AsyncSession,
        user_id: int,
        question_id: int | None = None,
        custom_question_id: int | None = None,
    ) -> WrongMasteryStatus:
        """
        做题答错时更新掌握状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题库题目 ID
        :param custom_question_id: 自定义错题 ID
        :return:
        """
        return await mastery_dao.on_wrong(db, user_id, question_id, custom_question_id)

    @staticmethod
    async def on_review(
        *,
        db: AsyncSession,
        user_id: int,
        question_id: int | None = None,
        custom_question_id: int | None = None,
    ) -> WrongMasteryStatus:
        """
        复盘时更新掌握状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题库题目 ID
        :param custom_question_id: 自定义错题 ID
        :return:
        """
        return await mastery_dao.on_review(db, user_id, question_id, custom_question_id)

    @staticmethod
    async def mark_as_mastered(
        *,
        db: AsyncSession,
        user_id: int,
        question_id: int | None = None,
        custom_question_id: int | None = None,
    ) -> WrongMasteryStatus:
        """
        手动标记为已掌握

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题库题目 ID
        :param custom_question_id: 自定义错题 ID
        :return:
        """
        return await mastery_dao.mark_as_mastered(db, user_id, question_id, custom_question_id)

    @staticmethod
    async def get_stats(
        *,
        db: AsyncSession,
        user_id: int,
    ) -> GetMasteryStatsResponse:
        """
        获取用户掌握状态统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stats = await mastery_dao.get_stats(db, user_id)
        total = stats['learning'] + stats['mastered'] + stats['forgotten']
        return GetMasteryStatsResponse(
            learning=stats['learning'],
            mastered=stats['mastered'],
            forgotten=stats['forgotten'],
            total=total,
        )

    @staticmethod
    async def get_forgotten_list(
        *,
        db: AsyncSession,
        user_id: int,
    ) -> list[GetForgottenItem]:
        """
        获取遗忘题目列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        forgotten = await mastery_dao.get_forgotten_list(db, user_id)
        return [GetForgottenItem.model_validate(item) for item in forgotten]

    @staticmethod
    async def check_and_mark_forgotten(
        *,
        db: AsyncSession,
        user_id: int,
    ) -> int:
        """
        检查并标记遗忘的题目

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return: 标记为遗忘的题目数量
        """
        return await mastery_dao.check_and_mark_forgotten(db, user_id)


mastery_service: MasteryService = MasteryService()
