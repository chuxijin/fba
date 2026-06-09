#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.study_plan.crud import study_plan_dao, study_plan_item_dao
from backend.app.study_plan.model.item import StudyPlanItem
from backend.app.study_plan.model.plan import StudyPlan
from backend.app.study_plan.schema.item import GetStudyPlanItemDetail
from backend.app.study_plan.schema.plan import StudyPlanProgress
from backend.app.study_plan.schema.today import TodayStudyPlanDetail
from backend.common.exception import errors
from backend.utils.timezone import timezone


def _calc_day_index(plan: StudyPlan, target_date: date) -> tuple[int, int]:
    """
    根据严格日历策略计算 day_index 和 total_days

    :param plan: 学习计划
    :param target_date: 目标日期
    :return:
    """
    day_index = (target_date - plan.start_date).days + 1
    total_days = (plan.end_date - plan.start_date).days + 1
    return day_index, total_days


def _calc_progress(items: list[StudyPlanItem]) -> StudyPlanProgress:
    """
    计算计划项列表的完成进度

    :param items: 计划项列表
    :return:
    """
    completed = sum(1 for it in items if it.status == 'completed')
    total = len(items)
    percent = int(completed * 100 / total) if total else 0
    return StudyPlanProgress(completed=completed, total=total, percent=percent)


async def get_today_plan(db: AsyncSession, user_id: int) -> TodayStudyPlanDetail:
    """
    获取学员的今日计划聚合视图

    :param db: 数据库会话
    :param user_id: 学员用户 ID
    :return:
    """
    today = timezone.now().date()
    plan = await study_plan_dao.get_by_user_covering_date(db, user_id, today)
    if plan is None:
        raise errors.NotFoundError(msg='您当前没有进行中的学习计划')

    items = list(await study_plan_item_dao.list_by_user_and_date(db, user_id, today))
    day_index, total_days = _calc_day_index(plan, today)

    return TodayStudyPlanDetail(
        plan_id=plan.id,
        plan_title=plan.title,
        today=today,
        day_index=day_index,
        total_days=total_days,
        items=[GetStudyPlanItemDetail.model_validate(it) for it in items],
        progress=_calc_progress(items),
    )


async def count_uncompleted_history(
    db: AsyncSession, user_id: int, before_date: date | None = None,
) -> int:
    """
    统计学员历史上未完成的计划项数量（用于今日页提醒铃铛）

    :param db: 数据库会话
    :param user_id: 学员用户 ID
    :param before_date: 截止日期（默认今天）
    :return:
    """
    target = before_date or timezone.now().date()
    stmt = select(func.count(StudyPlanItem.id)).where(
        StudyPlanItem.user_id == user_id,
        StudyPlanItem.plan_date < target,
        StudyPlanItem.status == 'skipped',
        StudyPlanItem.deleted == 0,
    )
    result = await db.execute(stmt)
    return result.scalar() or 0
