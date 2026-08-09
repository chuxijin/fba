#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.service.wrong_review_service import wrong_review_service


async def select_wrong_review_questions(
    db: AsyncSession,
    user_id: int,
    limit: int = 10,
) -> list[int]:
    """
    选取学员需要复盘的错题 ID 列表

    直接复用题库 v2 的到期重练队列（next_practice_time <= now，按最该练的优先）。
    v2 的阶梯排期是错题推送的唯一真相源，学习计划不再自建时间窗口，避免两处推送给出不同题目。
    返回空列表是允许的业务结果（学员没有到期错题），调用方需做兜底提示

    :param db: 数据库会话
    :param user_id: 学员用户 ID
    :param limit: 返回题目数量上限
    :return:
    """
    result = await wrong_review_service.get_due(db=db, user_id=user_id, limit=limit)
    return [item.question_id for item in result.items]
