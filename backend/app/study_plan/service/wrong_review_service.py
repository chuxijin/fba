#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.model.practice import WrongQuestionBook
from backend.utils.timezone import timezone


async def select_wrong_review_questions(
    db: AsyncSession,
    user_id: int,
    limit: int = 10,
    recent_days: int = 30,
) -> list[int]:
    """
    选取学员需要复盘的错题 ID 列表

    MVP 策略（D20）：近 N 天内 + 未掌握，按 last_wrong_time DESC 取前 limit 道
    返回空列表是允许的业务结果（学员近期没错题），调用方需做兜底提示
    TODO（U10）：未来需对接能力评估模型，按知识点薄弱程度智能推荐

    :param db: 数据库会话
    :param user_id: 学员用户 ID
    :param limit: 返回题目数量上限
    :param recent_days: 时间窗口（天）；默认 30 天匹配公考备考节奏
    :return:
    """
    since = timezone.now() - timedelta(days=recent_days)
    stmt = (
        select(WrongQuestionBook.question_id)
        .where(
            WrongQuestionBook.user_id == user_id,
            WrongQuestionBook.is_mastered.is_(False),
            WrongQuestionBook.last_wrong_time.is_not(None),
            WrongQuestionBook.last_wrong_time >= since,
            WrongQuestionBook.deleted == 0,
        )
        .order_by(WrongQuestionBook.last_wrong_time.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [row for row in result.scalars().all()]
