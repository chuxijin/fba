#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学员端业务编排服务（启动 / 完成模块）"""

from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.schema.practice import CreatePracticeSessionParam, CreateSessionFromIdsParam
from backend.app.question_bank.service.session_service import session_service
from backend.app.study_plan.crud import study_plan_dao, study_plan_item_dao
from backend.app.study_plan.model.item import StudyPlanItem
from backend.app.study_plan.model.plan import StudyPlan
from backend.app.study_plan.model.record import StudyPlanRecord
from backend.app.study_plan.schema.item import (
    CompleteStudyPlanItemParam,
    StartStudyPlanItemResult,
)
from backend.app.study_plan.service.completion import check_completion
from backend.app.study_plan.service.wrong_review_service import select_wrong_review_questions
from backend.common.exception import errors


async def _ensure_practice_session(
    db: AsyncSession,
    item: StudyPlanItem,
) -> str:
    """
    刷题类按需创建题库练习会话；已存在则复用

    :param db: 数据库会话
    :param item: 计划项
    :return:
    """
    extra = dict(item.extra or {})
    existing = extra.get('session_key')
    if isinstance(existing, str) and existing:
        session = await practice_session_dao.get_by_key(db, existing)
        if session is not None and session.user_id == item.user_id and session.status == 'in_progress':
            return existing

        extra.pop('session_key', None)

    if item.ref_type != 'question_set':
        raise errors.RequestError(msg='刷题模块引用类型必须为 question_set')

    question_ids = _parse_positive_int_list(extra.get('question_ids'), limit=500)
    if question_ids:
        create_from_ids_param = CreateSessionFromIdsParam(
            question_ids=question_ids,
            session_type='bank',
            practice_name=item.title,
            bank_id=item.ref_id if item.ref_id else None,
        )
        session = await session_service.create_session_from_ids(
            db=db,
            user_id=item.user_id,
            obj=create_from_ids_param,
        )

        extra['session_key'] = session.session_key
        await study_plan_item_dao.update_extra(db, item.id, extra)
        item.extra = extra
        return session.session_key

    knowledge_points = _parse_knowledge_points(extra)
    if item.ref_id is None and not knowledge_points:
        raise errors.RequestError(msg='刷题模块未配置题库、知识点或题目 ID 列表')

    create_param = CreatePracticeSessionParam(
        session_type='bank' if item.ref_id is not None else 'random',
        practice_name=item.title,
        bank_id=item.ref_id,
        chapter_id=_parse_positive_int(extra.get('chapter_id')),
        cat_id=_parse_positive_int(extra.get('cat_id')),
        year_start=_parse_year(extra.get('year_start')),
        year_end=_parse_year(extra.get('year_end')),
        region=_parse_text(extra.get('region')),
        knowledge_point=knowledge_points,
        limit=_parse_limited_positive_int(extra.get('question_count'), max_value=500),
        shuffle=bool(extra.get('shuffle', False)),
        question_types=_parse_question_types(extra.get('question_types')),
        exam_config=_build_exam_config(extra),
    )
    session = await session_service.create_unified_session(
        db=db,
        user_id=item.user_id,
        obj=create_param,
    )

    extra['session_key'] = session.session_key
    await study_plan_item_dao.update_extra(db, item.id, extra)
    item.extra = extra
    return session.session_key


def _parse_positive_int(value: Any) -> int | None:
    """
    解析正整数

    :param value: 原始值
    :return:
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        if parsed > 0:
            return parsed
    return None


def _parse_limited_positive_int(value: Any, max_value: int) -> int | None:
    """
    解析带上限的正整数

    :param value: 原始值
    :param max_value: 最大值
    :return:
    """
    parsed = _parse_positive_int(value)
    if parsed is None:
        return None
    return min(parsed, max_value)


def _parse_year(value: Any) -> int | None:
    """
    解析题库年份条件

    :param value: 原始值
    :return:
    """
    parsed = _parse_positive_int(value)
    if parsed is None:
        return None
    if 1900 <= parsed <= 2100:
        return parsed
    return None


def _parse_positive_int_list(value: Any, limit: int | None = None) -> list[int]:
    """
    解析正整数列表

    :param value: 原始值
    :param limit: 最大返回数量
    :return:
    """
    if not isinstance(value, list):
        return []

    result: list[int] = []
    seen: set[int] = set()
    for item in value:
        parsed = _parse_positive_int(item)
        if parsed is None or parsed in seen:
            continue
        seen.add(parsed)
        result.append(parsed)
        if limit is not None and len(result) >= limit:
            break
    return result


def _parse_text(value: Any) -> str | None:
    """
    解析非空文本

    :param value: 原始值
    :return:
    """
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None
    return text


def _parse_text_list(value: Any) -> list[str] | None:
    """
    解析非空文本列表

    :param value: 原始值
    :return:
    """
    if not isinstance(value, list):
        return None

    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _parse_text(item)
        if text is None or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result or None


def _parse_question_types(value: Any) -> list[str] | None:
    """
    解析题型过滤条件

    :param value: 原始值
    :return:
    """
    allowed_types = {'single', 'multiple', 'judgement', 'fill', 'shortAnswer'}
    result = _parse_text_list(value)
    if result is None:
        return None

    filtered = [item for item in result if item in allowed_types]
    return filtered or None


def _parse_knowledge_points(extra: dict[str, Any]) -> list[Any] | None:
    """
    解析刷题知识点筛选条件

    :param extra: 计划项扩展配置
    :return:
    """
    value = extra.get('knowledge_points')
    if value is None:
        value = extra.get('knowledge_point')
    if not isinstance(value, list):
        return None

    result = [item for item in value if item not in (None, '')]
    return result or None


def _build_exam_config(extra: dict[str, Any]) -> dict[str, Any] | None:
    """
    构建题库会话考试配置

    :param extra: 计划项扩展配置
    :return:
    """
    config: dict[str, Any] = {}
    practice_mode = _parse_text(extra.get('practice_mode'))
    if practice_mode:
        config['practice_mode'] = practice_mode

    time_limit = _parse_positive_int(extra.get('time_limit'))
    if time_limit is not None:
        config['time_limit'] = time_limit

    return config or None


async def get_item_for_user(
    db: AsyncSession,
    item_id: int,
    user_id: int,
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


async def get_plan_for_user(db: AsyncSession, plan_id: int, user_id: int) -> StudyPlan:
    """
    获取计划并校验归属（学员视角）

    :param db: 数据库会话
    :param plan_id: 计划 ID
    :param user_id: 学员用户 ID
    :return:
    """
    plan = await study_plan_dao.get(db, plan_id)
    if plan is None:
        raise errors.NotFoundError(msg='计划不存在')
    if plan.user_id != user_id:
        raise errors.ForbiddenError(msg='不是您的计划')
    return plan


async def list_items_of_my_plan(
    db: AsyncSession,
    plan_id: int,
    user_id: int,
) -> Sequence[StudyPlanItem]:
    """
    获取学员某计划的全部 items（按 plan_date + order_index）

    :param db: 数据库会话
    :param plan_id: 计划 ID
    :param user_id: 学员用户 ID
    :return:
    """
    await get_plan_for_user(db, plan_id, user_id)
    return await study_plan_item_dao.list_by_plan(db, plan_id)


async def get_plan_progress_for_user(
    db: AsyncSession,
    plan_id: int,
    user_id: int,
) -> dict[str, int]:
    """
    计算学员某计划的整体完成进度

    :param db: 数据库会话
    :param plan_id: 计划 ID
    :param user_id: 学员用户 ID
    :return:
    """
    await get_plan_for_user(db, plan_id, user_id)
    items = await study_plan_item_dao.list_by_plan(db, plan_id)
    completed = sum(1 for it in items if it.status == 'completed')
    total = len(items)
    percent = int(completed * 100 / total) if total else 0
    return {'completed': completed, 'total': total, 'percent': percent}


async def start_item(
    db: AsyncSession,
    item_id: int,
    user_id: int,
) -> StartStudyPlanItemResult:
    """
    启动计划项；wrong_review 实时算错题；practice 按需绑定题库 session

    :param db: 数据库会话
    :param item_id: 计划项 ID
    :param user_id: 学员用户 ID
    :return:
    """
    item = await get_item_for_user(db, item_id, user_id)
    if item.status == 'completed':
        raise errors.RequestError(msg='该模块已完成')

    payload: dict[str, Any] | None = None
    skip_status_update = False

    if item.module_type == 'wrong_review':
        question_ids = await select_wrong_review_questions(db, user_id, limit=10)
        payload = {
            'question_ids': question_ids,
            'empty_hint': '近期没有需要复盘的错题，要不要做点新题？' if not question_ids else None,
        }
    elif item.module_type == 'practice':
        session_key = await _ensure_practice_session(db, item)
        payload = {'session_key': session_key}
    elif item.module_type == 'resource':
        extra = item.extra or {}
        cloud_links = extra.get('cloud_links') if isinstance(extra.get('cloud_links'), list) else []
        payload = {
            'cloud_links': cloud_links,
            'empty_hint': '该资源模块尚未配置链接' if not cloud_links else None,
        }
        if not cloud_links:
            skip_status_update = True

    if item.status == 'pending' and not skip_status_update:
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
