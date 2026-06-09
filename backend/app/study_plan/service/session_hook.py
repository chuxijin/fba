#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题库 session 完成/放弃回调（由 question_bank API 层 lazy import 调用）"""
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.study_plan.crud import study_plan_item_dao
from backend.common.log import log


async def handle_session_completed(
    db: AsyncSession,
    *,
    session_key: str,
    user_id: int,
    correct_count: int,
    total_count: int,
) -> None:
    """
    题库 session 交卷后回调：自动完成关联的 plan_item

    考试模式语义：交卷 = 完成，分数是导师看的数据维度，不卡学员进度。
    不做 completion check，直接标 completed 并写 record。

    :param db: 数据库会话
    :param session_key: 题库练习会话 key
    :param user_id: 学员用户 ID
    :param correct_count: 正确题数
    :param total_count: 已答题数
    :return:
    """
    item = await study_plan_item_dao.get_by_session_key(db, session_key)
    if item is None:
        return
    if item.user_id != user_id:
        return
    if item.status == 'completed':
        return

    from backend.app.study_plan.model.record import StudyPlanRecord

    record = StudyPlanRecord(
        item_id=item.id,
        user_id=user_id,
        duration_seconds=0,
        correct_count=correct_count,
        total_count=total_count,
        extra_data={'source': 'session_auto', 'session_key': session_key},
    )
    db.add(record)
    await db.flush()

    await study_plan_item_dao.update_status(db, item.id, 'completed')
    log.info(
        'session_hook: plan_item {} session_key={} 自动完成 (correct={}/{})',
        item.id, session_key, correct_count, total_count,
    )


async def handle_session_abandoned(
    db: AsyncSession,
    *,
    session_key: str,
    user_id: int,
) -> None:
    """
    题库 session 放弃后回调：清除 plan_item 的 session_key 绑定

    session 已 abandoned 无法复用，清除后下次点"开始练习"会 lazy 创建新 session。
    plan_item 保持 in_progress，不标 skipped。

    :param db: 数据库会话
    :param session_key: 题库练习会话 key
    :param user_id: 学员用户 ID
    :return:
    """
    item = await study_plan_item_dao.get_by_session_key(db, session_key)
    if item is None:
        return
    if item.user_id != user_id:
        return
    if item.status == 'completed':
        return

    extra = dict(item.extra or {})
    extra.pop('session_key', None)
    await study_plan_item_dao.update_extra(db, item.id, extra)
    log.info(
        'session_hook: plan_item {} session_key={} 清除绑定，下次进入将创建新 session',
        item.id, session_key,
    )
