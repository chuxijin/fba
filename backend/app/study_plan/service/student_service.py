#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学员端业务编排服务（启动 / 完成模块）"""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.study_plan.crud import study_plan_item_dao, study_plan_record_dao
from backend.app.study_plan.model.item import StudyPlanItem
from backend.app.study_plan.model.record import StudyPlanRecord
from backend.app.study_plan.schema.item import (
    CompleteStudyPlanItemParam,
    StartStudyPlanItemResult,
)
from backend.app.study_plan.service.completion import check_completion
from backend.app.study_plan.service.wrong_review_service import select_wrong_review_questions
from backend.common.exception import errors


async def get_item_for_user(
    db: AsyncSession, item_id: int, user_id: int,
) -> StudyPlanItem:
    """
    获取计划项并校验归属

    :param db: 数据库会话
    :param item_id: 计划项 ID
    :param user_id: 学员用户 ID
    :return:
    """
    item = await study_plan_item_dao.get(db, item_id)
    if item is None:
        raise errors.NotFoundError(msg='计划项不存在')
    if item.user_id != user_id:
        raise errors.ForbiddenError(msg='不是您的计划项')
    return item


async def start_item(
    db: AsyncSession, item_id: int, user_id: int,
) -> StartStudyPlanItemResult:
    """
    启动计划项；wrong_review 类型实时计算错题列表

    :param db: 数据库会话
    :param item_id: 计划项 ID
    :param user_id: 学员用户 ID
    :return:
    """
    item = await get_item_for_user(db, item_id, user_id)
    if item.status == 'completed':
        raise errors.RequestError(msg='该模块已完成')

    payload: dict[str, Any] | None = None

    if item.module_type == 'wrong_review':
        question_ids = await select_wrong_review_questions(db, user_id, limit=10)
        payload = {
            'question_ids': question_ids,
            'empty_hint': '近期没有需要复盘的错题，要不要做点新题？' if not question_ids else None,
        }

    if item.status == 'pending':
        await study_plan_item_dao.update_status(db, item_id, 'in_progress')
        item.status = 'in_progress'

    return StartStudyPlanItemResult(
        item_id=item.id,
        status=item.status,
        payload=payload,
    )


async def complete_item(
    db: AsyncSession,
    item_id: int,
    user_id: int,
    param: CompleteStudyPlanItemParam,
) -> StudyPlanRecord:
    """
    提交计划项完成；服务端做完成判定，通过后写记录并标记 completed

    :param db: 数据库会话
    :param item_id: 计划项 ID
    :param user_id: 学员用户 ID
    :param param: 完成提交参数
    :return:
    """
    item = await get_item_for_user(db, item_id, user_id)
    if item.status == 'completed':
        raise errors.RequestError(msg='该模块已完成，无需重复提交')

    payload = param.model_dump(exclude_none=False)
    check = check_completion(item, payload)
    if not check.ok:
        raise errors.RequestError(msg=check.reason or '完成条件未满足')

    record = StudyPlanRecord(
        item_id=item.id,
        user_id=user_id,
        duration_seconds=param.duration_seconds,
        score=param.score,
        correct_count=param.correct_count,
        total_count=param.total_count,
        extra_data=param.extra_data,
    )
    db.add(record)
    await db.flush()

    await study_plan_item_dao.update_status(db, item_id, 'completed')
    return record
