#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from math import exp
from typing import Any

import sqlalchemy as sa

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model.category import Category
from backend.app.question_bank.model import PracticeSession, Question, SessionQuestion
from backend.app.study_plan.crud import (
    study_ability_attempt_dao,
    study_ability_catalog_dao,
    study_ability_category_binding_dao,
    study_plan_record_dao,
    study_user_category_profile_dao,
)
from backend.app.study_plan.model.ability_profile import (
    StudyAbilityAttempt,
    StudyAbilityAttemptCategory,
    StudyAbilityCategoryBinding,
    StudyUserCategoryProfile,
)
from backend.app.study_plan.schema.ability import (
    BatchSubmitStudyAbilityAttemptParam,
    BatchSubmitStudyAbilityAttemptResult,
    GetStudyAbilityAttemptDetail,
    GetStudyUserCategoryProfileDetail,
    SubmitStudyAbilityAttemptParam,
    SubmitStudyAbilityAttemptResult,
)
from backend.app.study_plan.schema.item import CompleteStudyPlanItemParam
from backend.app.study_plan.service.ability_catalog import get_ability_catalog_item
from backend.app.study_plan.service.student_service import complete_item
from backend.common.exception import errors
from backend.utils.timezone import timezone

ALGORITHM_VERSION = 'ability_profile_v1'
DEFAULT_TARGET_ACCURACY = Decimal('0.75')
QUESTION_BANK_BENCHMARK_SECONDS = Decimal('90')
QBANK_CATEGORY_APP_CODE = 'youanshang'
SOURCE_TYPE_ABILITY = 'ability'
SOURCE_TYPE_QUESTION_BANK = 'question_bank'


@dataclass(slots=True)
class QuestionBankCategoryContribution:
    """题库答题分类贡献"""

    category_id: int
    total_count: int
    correct_count: int
    duration_seconds: int
    completed_at: datetime


@dataclass(slots=True)
class QuestionBankCategoryLookup:
    """题库知识点分类匹配结果"""

    id_set: set[int]
    code_to_id: dict[str, int]
    name_to_id: dict[str, int]


async def submit_ability_attempt(
    db: AsyncSession,
    user_id: int,
    param: SubmitStudyAbilityAttemptParam,
) -> SubmitStudyAbilityAttemptResult:
    """
    提交能力练习记录并更新画像

    :param db: 数据库会话
    :param user_id: 学员用户 ID
    :param param: 提交参数
    :return:
    """
    existing = await study_ability_attempt_dao.get_by_client_session(db, user_id, param.client_session_id)
    if existing is not None:
        return SubmitStudyAbilityAttemptResult(
            attempt=GetStudyAbilityAttemptDetail.model_validate(existing),
            profile_updated_count=0,
            study_plan_synced=existing.study_plan_record_id is not None,
            study_plan_error=None,
        )

    _validate_counts(param.total_count, param.correct_count, param.wrong_count)
    wrong_count = _resolve_wrong_count(param.total_count, param.correct_count, param.wrong_count)
    completed_at = _resolve_completed_at(param.completed_at)
    score = _resolve_attempt_score(param.score, param.total_count, param.correct_count)
    avg_seconds = _resolve_avg_seconds(param.avg_seconds, param.duration_seconds, param.total_count)
    catalog_config = await _resolve_catalog_config(db, param.ability_key)

    attempt = StudyAbilityAttempt(
        user_id=user_id,
        ability_key=param.ability_key,
        mode=param.mode,
        difficulty=param.difficulty,
        source=param.source,
        study_plan_item_id=param.study_plan_item_id,
        client_session_id=param.client_session_id,
        total_count=param.total_count,
        correct_count=param.correct_count,
        wrong_count=wrong_count,
        duration_seconds=param.duration_seconds,
        avg_seconds=avg_seconds,
        score=score,
        metric_data=_build_metric_data(param, catalog_config),
        records=param.records,
        completed_at=completed_at,
        completed_date=completed_at.date(),
    )
    db.add(attempt)
    await db.flush()

    study_plan_synced, study_plan_error = await _sync_study_plan_result(
        db=db,
        user_id=user_id,
        param=param,
        attempt=attempt,
        score=score,
        catalog_config=catalog_config,
    )

    bindings = await study_ability_category_binding_dao.list_by_ability_mode(db, param.ability_key, param.mode)
    profile_updated_count = await _write_category_contributions(
        db=db,
        attempt=attempt,
        bindings=bindings,
        target_accuracy=catalog_config['target_accuracy'],
        benchmark_seconds=catalog_config['benchmark_seconds'],
    )
    await db.flush()

    return SubmitStudyAbilityAttemptResult(
        attempt=GetStudyAbilityAttemptDetail.model_validate(attempt),
        profile_updated_count=profile_updated_count,
        study_plan_synced=study_plan_synced,
        study_plan_error=study_plan_error,
    )


async def batch_submit_ability_attempts(
    db: AsyncSession,
    user_id: int,
    param: BatchSubmitStudyAbilityAttemptParam,
) -> BatchSubmitStudyAbilityAttemptResult:
    """
    批量提交能力练习记录

    :param db: 数据库会话
    :param user_id: 学员用户 ID
    :param param: 批量提交参数
    :return:
    """
    results: list[SubmitStudyAbilityAttemptResult] = []
    for attempt_param in param.attempts:
        result = await submit_ability_attempt(db, user_id, attempt_param)
        results.append(result)

    return BatchSubmitStudyAbilityAttemptResult(total=len(param.attempts), results=results)


async def list_user_category_profiles(
    db: AsyncSession,
    user_id: int,
    source_type: str | None = SOURCE_TYPE_ABILITY,
    category_id: int | None = None,
    include_children: bool = True,
) -> list[GetStudyUserCategoryProfileDetail]:
    """
    获取用户分类画像

    :param db: 数据库会话
    :param user_id: 学员用户 ID
    :param source_type: 来源类型
    :param category_id: 分类 ID
    :param include_children: 是否包含子孙分类
    :return:
    """
    category_ids = await _resolve_profile_category_ids(db, category_id, include_children)
    if category_id is not None and not category_ids:
        return []

    join_condition = sa.and_(
        Category.id == StudyUserCategoryProfile.category_id,
        Category.deleted == 0,
    )
    filters = [
        StudyUserCategoryProfile.user_id == user_id,
        StudyUserCategoryProfile.deleted == 0,
    ]
    if source_type:
        filters.append(StudyUserCategoryProfile.source_type == source_type)
    if category_ids:
        filters.append(StudyUserCategoryProfile.category_id.in_(category_ids))

    stmt = (
        select(StudyUserCategoryProfile, Category)
        .outerjoin(Category, join_condition)
        .where(*filters)
        .order_by(
            StudyUserCategoryProfile.weakness_score.desc(),
            StudyUserCategoryProfile.updated_time.desc(),
            StudyUserCategoryProfile.id.desc(),
        )
    )
    result = await db.execute(stmt)
    return [_build_profile_detail(profile, category) for profile, category in result.all()]


async def _resolve_profile_category_ids(
    db: AsyncSession,
    category_id: int | None,
    include_children: bool,
) -> list[int]:
    """
    解析画像分类过滤范围

    :param db: 数据库会话
    :param category_id: 分类 ID
    :param include_children: 是否包含子孙分类
    :return:
    """
    if category_id is None:
        return []
    if include_children:
        anchor = select(Category.id).where(
            Category.id == category_id,
            Category.deleted == 0,
        )
        cte = anchor.cte('profile_category_tree', recursive=True)
        recursive_part = select(Category.id).join(cte, Category.parent_id == cte.c.id).where(Category.deleted == 0)
        category_tree = cte.union_all(recursive_part)
        stmt = (
            select(Category.id)
            .join(category_tree, Category.id == category_tree.c.id)
            .where(
                Category.app_code == QBANK_CATEGORY_APP_CODE,
                Category.status.is_(True),
                Category.deleted == 0,
            )
        )
    else:
        stmt = select(Category.id).where(
            Category.id == category_id,
            Category.app_code == QBANK_CATEGORY_APP_CODE,
            Category.status.is_(True),
            Category.deleted == 0,
        )

    result = await db.execute(stmt)
    return [int(item) for item in result.scalars().all()]


async def sync_question_bank_session_profile(
    db: AsyncSession,
    user_id: int,
    session_id: int,
    completed_at: datetime | None = None,
) -> int:
    """
    同步题库会话答题数据到用户分类画像

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param session_id: 题库会话 ID
    :param completed_at: 完成时间
    :return:
    """
    session = await db.get(PracticeSession, session_id)
    if session is None or session.user_id != user_id:
        return 0
    if _is_question_bank_profile_synced(session):
        return 0

    rows = await _list_question_bank_session_rows(db, user_id, session_id)
    if not rows:
        return 0

    lookup = await _resolve_question_bank_category_lookup(
        db,
        [question.knowledge_point for _record, question in rows],
    )
    if not lookup.id_set and not lookup.code_to_id and not lookup.name_to_id:
        return 0

    profile_completed_at = _resolve_completed_at(completed_at)
    contributions: dict[int, QuestionBankCategoryContribution] = {}
    for record, question in rows:
        category_ids = _resolve_question_category_ids(question.knowledge_point, lookup)
        if not category_ids:
            continue

        duration_seconds = max(0, int(record.answer_time or 0))
        correct_count = 1 if record.is_correct else 0
        for category_id in category_ids:
            contribution = contributions.get(category_id)
            if contribution is None:
                contributions[category_id] = QuestionBankCategoryContribution(
                    category_id=category_id,
                    total_count=1,
                    correct_count=correct_count,
                    duration_seconds=duration_seconds,
                    completed_at=profile_completed_at,
                )
                continue

            contribution.total_count += 1
            contribution.correct_count += correct_count
            contribution.duration_seconds += duration_seconds

    if not contributions:
        return 0

    for contribution in contributions.values():
        await _upsert_profile_by_values(
            db=db,
            user_id=user_id,
            category_id=contribution.category_id,
            source_type=SOURCE_TYPE_QUESTION_BANK,
            attempt_count=1,
            total_count=contribution.total_count,
            correct_count=contribution.correct_count,
            duration_seconds=contribution.duration_seconds,
            completed_at=contribution.completed_at,
            target_accuracy=DEFAULT_TARGET_ACCURACY,
            benchmark_seconds=QUESTION_BANK_BENCHMARK_SECONDS,
        )

    _mark_question_bank_profile_synced(session, profile_completed_at)
    return len(contributions)


async def _list_question_bank_session_rows(
    db: AsyncSession,
    user_id: int,
    session_id: int,
) -> Sequence[tuple[SessionQuestion, Question]]:
    """
    获取题库会话已判题记录

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param session_id: 会话 ID
    :return:
    """
    stmt = (
        select(SessionQuestion, Question)
        .join(Question, SessionQuestion.question_id == Question.id)
        .where(
            SessionQuestion.session_id == session_id,
            SessionQuestion.user_id == user_id,
            SessionQuestion.is_correct.isnot(None),
            Question.knowledge_point.isnot(None),
        )
        .order_by(SessionQuestion.seq_no.asc(), SessionQuestion.id.asc())
    )
    result = await db.execute(stmt)
    return result.all()


async def _resolve_question_bank_category_lookup(
    db: AsyncSession,
    raw_values: Sequence[Any],
) -> QuestionBankCategoryLookup:
    """
    解析题目知识点到系统分类

    :param db: 数据库会话
    :param raw_values: 题目 knowledge_point 原始值
    :return:
    """
    category_ids: set[int] = set()
    terms: set[str] = set()
    for raw_value in raw_values:
        raw_ids, raw_terms = _extract_knowledge_point_refs(raw_value)
        category_ids.update(raw_ids)
        terms.update(raw_terms)

    conditions: list[Any] = []
    if category_ids:
        conditions.append(Category.id.in_(category_ids))
    if terms:
        conditions.append(Category.code.in_(terms))
        conditions.append(Category.name.in_(terms))
    if not conditions:
        return QuestionBankCategoryLookup(id_set=set(), code_to_id={}, name_to_id={})

    stmt = select(Category.id, Category.code, Category.name).where(
        Category.app_code == QBANK_CATEGORY_APP_CODE,
        Category.type == 'knowledge_point',
        Category.status.is_(True),
        Category.deleted == 0,
        sa.or_(*conditions),
    )
    rows = (await db.execute(stmt)).all()

    id_set: set[int] = set()
    code_to_id: dict[str, int] = {}
    name_to_id: dict[str, int] = {}
    for row in rows:
        category_id = int(row[0])
        id_set.add(category_id)
        if row[1]:
            code_to_id[str(row[1]).strip()] = category_id
        if row[2]:
            name_to_id[str(row[2]).strip()] = category_id

    return QuestionBankCategoryLookup(
        id_set=id_set,
        code_to_id=code_to_id,
        name_to_id=name_to_id,
    )


def _resolve_question_category_ids(raw_value: Any, lookup: QuestionBankCategoryLookup) -> list[int]:
    """
    将单题知识点解析为分类 ID 列表

    :param raw_value: 题目 knowledge_point 原始值
    :param lookup: 分类匹配结果
    :return:
    """
    raw_ids, terms = _extract_knowledge_point_refs(raw_value)
    category_ids: set[int] = set()
    for category_id in raw_ids:
        if category_id in lookup.id_set:
            category_ids.add(category_id)

    for term in terms:
        code_category_id = lookup.code_to_id.get(term)
        if code_category_id is not None:
            category_ids.add(code_category_id)

        name_category_id = lookup.name_to_id.get(term)
        if name_category_id is not None:
            category_ids.add(name_category_id)

    return sorted(category_ids)


def _extract_knowledge_point_refs(raw_value: Any) -> tuple[set[int], set[str]]:
    """
    提取知识点引用

    :param raw_value: 题目 knowledge_point 原始值
    :return:
    """
    category_ids: set[int] = set()
    terms: set[str] = set()

    if raw_value is None:
        return category_ids, terms

    values = raw_value if isinstance(raw_value, list) else [raw_value]
    for item in values:
        if isinstance(item, dict):
            for key in ('id', 'category_id', 'cat_id'):
                category_id = _parse_category_id(item.get(key))
                if category_id is not None:
                    category_ids.add(category_id)

            for key in ('code', 'name', 'label', 'title'):
                term = _parse_category_term(item.get(key))
                if term:
                    terms.add(term)
            continue

        category_id = _parse_category_id(item)
        if category_id is not None:
            category_ids.add(category_id)

        term = _parse_category_term(item)
        if term:
            terms.add(term)

    return category_ids, terms


def _parse_category_id(value: Any) -> int | None:
    """
    解析分类 ID

    :param value: 原始值
    :return:
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            parsed = int(text)
            return parsed if parsed > 0 else None
    return None


def _parse_category_term(value: Any) -> str | None:
    """
    解析分类编码或名称

    :param value: 原始值
    :return:
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _is_question_bank_profile_synced(session: PracticeSession) -> bool:
    """
    判断题库画像是否已同步

    :param session: 题库会话
    :return:
    """
    snapshot = session.source_snapshot or {}
    return bool(snapshot.get('question_bank_profile_synced_at'))


def _mark_question_bank_profile_synced(session: PracticeSession, completed_at: datetime) -> None:
    """
    标记题库画像已同步

    :param session: 题库会话
    :param completed_at: 完成时间
    :return:
    """
    snapshot = dict(session.source_snapshot or {})
    snapshot['question_bank_profile_synced_at'] = completed_at.isoformat()
    session.source_snapshot = snapshot


def _validate_counts(total_count: int, correct_count: int, wrong_count: int | None) -> None:
    """
    校验答题数量

    :param total_count: 总题数
    :param correct_count: 正确题数
    :param wrong_count: 错误题数
    :return:
    """
    if correct_count > total_count:
        raise errors.RequestError(msg='正确题数不能大于总题数')
    if wrong_count is not None and wrong_count > total_count:
        raise errors.RequestError(msg='错误题数不能大于总题数')
    if wrong_count is not None and correct_count + wrong_count > total_count:
        raise errors.RequestError(msg='正确题数与错误题数之和不能大于总题数')


def _resolve_wrong_count(total_count: int, correct_count: int, wrong_count: int | None) -> int:
    """
    计算错误题数

    :param total_count: 总题数
    :param correct_count: 正确题数
    :param wrong_count: 错误题数
    :return:
    """
    if wrong_count is not None:
        return wrong_count
    return max(0, total_count - correct_count)


def _resolve_completed_at(completed_at: datetime | None) -> datetime:
    """
    解析完成时间

    :param completed_at: 客户端完成时间
    :return:
    """
    if completed_at is None:
        return timezone.now()
    return timezone.from_datetime(completed_at)


def _resolve_attempt_score(score: float | None, total_count: int, correct_count: int) -> Decimal | None:
    """
    解析标准化得分

    :param score: 客户端得分
    :param total_count: 总题数
    :param correct_count: 正确题数
    :return:
    """
    if score is not None:
        return _to_decimal(score, '0.01')
    if total_count <= 0:
        return None
    return _to_decimal(correct_count / total_count * 100, '0.01')


def _resolve_avg_seconds(avg_seconds: float | None, duration_seconds: int, total_count: int) -> Decimal | None:
    """
    解析平均耗时

    :param avg_seconds: 客户端平均耗时
    :param duration_seconds: 总耗时秒
    :param total_count: 总题数
    :return:
    """
    if avg_seconds is not None:
        return _to_decimal(avg_seconds, '0.01')
    if total_count <= 0:
        return None
    return _to_decimal(duration_seconds / total_count, '0.01')


async def _resolve_catalog_config(db: AsyncSession, ability_key: str) -> dict[str, Any]:
    """
    解析能力目录配置

    :param db: 数据库会话
    :param ability_key: 能力标识
    :return:
    """
    target_accuracy = DEFAULT_TARGET_ACCURACY
    benchmark_seconds: Decimal | None = None
    ability_title: str | None = None

    catalog = await study_ability_catalog_dao.get_by_key(db, ability_key)
    if catalog is not None:
        ability_title = catalog.title
        if catalog.default_accuracy is not None:
            target_accuracy = _to_decimal(catalog.default_accuracy, '0.0001') or DEFAULT_TARGET_ACCURACY
        if catalog.benchmark_seconds is not None:
            benchmark_seconds = _to_decimal(catalog.benchmark_seconds, '0.01')
    else:
        static_catalog = get_ability_catalog_item(ability_key)
        if static_catalog is not None:
            ability_title = static_catalog.title
            if static_catalog.default_accuracy is not None:
                target_accuracy = _to_decimal(static_catalog.default_accuracy, '0.0001') or DEFAULT_TARGET_ACCURACY
            if static_catalog.benchmark_seconds is not None:
                benchmark_seconds = _to_decimal(static_catalog.benchmark_seconds, '0.01')

    return {
        'ability_title': ability_title,
        'target_accuracy': target_accuracy,
        'benchmark_seconds': benchmark_seconds,
    }


def _build_metric_data(
    param: SubmitStudyAbilityAttemptParam,
    catalog_config: dict[str, Any],
) -> dict[str, Any] | None:
    """
    构建指标快照

    :param param: 提交参数
    :param catalog_config: 能力目录配置
    :return:
    """
    metric_data = dict(param.metric_data or {})
    if param.ability_title:
        metric_data['ability_title'] = param.ability_title
    elif catalog_config.get('ability_title'):
        metric_data['ability_title'] = catalog_config['ability_title']

    if catalog_config.get('target_accuracy') is not None:
        metric_data['target_accuracy'] = float(catalog_config['target_accuracy'])
    if catalog_config.get('benchmark_seconds') is not None:
        metric_data['benchmark_seconds'] = float(catalog_config['benchmark_seconds'])

    return metric_data or None


async def _sync_study_plan_result(
    *,
    db: AsyncSession,
    user_id: int,
    param: SubmitStudyAbilityAttemptParam,
    attempt: StudyAbilityAttempt,
    score: Decimal | None,
    catalog_config: dict[str, Any],
) -> tuple[bool, str | None]:
    """
    同步学习计划完成记录

    :param db: 数据库会话
    :param user_id: 学员用户 ID
    :param param: 提交参数
    :param attempt: 能力练习记录
    :param score: 标准化得分
    :param catalog_config: 能力目录配置
    :return:
    """
    if param.study_plan_item_id is None:
        return False, None

    complete_param = CompleteStudyPlanItemParam(
        duration_seconds=param.duration_seconds,
        score=_score_to_int(score),
        correct_count=param.correct_count,
        total_count=param.total_count,
        extra_data={
            'ability_attempt_id': attempt.id,
            'ability_key': param.ability_key,
            'ability_title': param.ability_title or catalog_config.get('ability_title'),
            'mode': param.mode,
            'difficulty': param.difficulty,
            'source': param.source,
            'metric_data': param.metric_data,
            'records': param.records,
        },
    )

    try:
        record = await complete_item(db, param.study_plan_item_id, user_id, complete_param)
    except errors.BaseExceptionError as exc:
        message = str(exc.msg or exc)
        if '已完成' in message:
            await _attach_latest_plan_record(db, user_id, param.study_plan_item_id, attempt)
            return True, None
        return False, message

    attempt.study_plan_record_id = record.id
    return True, None


async def _attach_latest_plan_record(
    db: AsyncSession,
    user_id: int,
    item_id: int,
    attempt: StudyAbilityAttempt,
) -> None:
    """
    关联已存在的计划完成记录

    :param db: 数据库会话
    :param user_id: 学员用户 ID
    :param item_id: 计划项 ID
    :param attempt: 能力练习记录
    :return:
    """
    record = await study_plan_record_dao.get_latest_by_item(db, item_id)
    if record is None or record.user_id != user_id:
        return
    attempt.study_plan_record_id = record.id


async def _write_category_contributions(
    *,
    db: AsyncSession,
    attempt: StudyAbilityAttempt,
    bindings: Sequence[StudyAbilityCategoryBinding],
    target_accuracy: Decimal,
    benchmark_seconds: Decimal | None,
) -> int:
    """
    写入分类贡献并更新用户画像

    :param db: 数据库会话
    :param attempt: 能力练习记录
    :param bindings: 分类绑定
    :param target_accuracy: 目标正确率
    :param benchmark_seconds: 速度基准秒
    :return:
    """
    updated_count = 0
    for binding in bindings:
        contribution = _build_attempt_category(attempt, binding)
        db.add(contribution)
        await _upsert_profile(
            db=db,
            contribution=contribution,
            target_accuracy=target_accuracy,
            benchmark_seconds=benchmark_seconds,
        )
        updated_count += 1

    return updated_count


def _build_attempt_category(
    attempt: StudyAbilityAttempt,
    binding: StudyAbilityCategoryBinding,
) -> StudyAbilityAttemptCategory:
    """
    构建分类贡献记录

    :param attempt: 能力练习记录
    :param binding: 分类绑定
    :return:
    """
    total_count = _weighted_int(attempt.total_count, binding.weight)
    correct_count = min(total_count, _weighted_int(attempt.correct_count, binding.weight))
    duration_seconds = _weighted_int(attempt.duration_seconds, binding.weight)

    return StudyAbilityAttemptCategory(
        attempt_id=attempt.id,
        user_id=attempt.user_id,
        category_id=binding.category_id,
        role=binding.role,
        weight=binding.weight,
        total_count=total_count,
        correct_count=correct_count,
        duration_seconds=duration_seconds,
        score=attempt.score,
        completed_at=attempt.completed_at,
        completed_date=attempt.completed_date,
    )


async def _upsert_profile(
    *,
    db: AsyncSession,
    contribution: StudyAbilityAttemptCategory,
    target_accuracy: Decimal,
    benchmark_seconds: Decimal | None,
) -> StudyUserCategoryProfile:
    """
    更新用户分类画像

    :param db: 数据库会话
    :param contribution: 分类贡献
    :param target_accuracy: 目标正确率
    :param benchmark_seconds: 速度基准秒
    :return:
    """
    return await _upsert_profile_by_values(
        db=db,
        user_id=contribution.user_id,
        category_id=contribution.category_id,
        source_type=SOURCE_TYPE_ABILITY,
        attempt_count=1,
        total_count=contribution.total_count,
        correct_count=contribution.correct_count,
        duration_seconds=contribution.duration_seconds,
        completed_at=contribution.completed_at,
        target_accuracy=target_accuracy,
        benchmark_seconds=benchmark_seconds,
    )


async def _upsert_profile_by_values(
    *,
    db: AsyncSession,
    user_id: int,
    category_id: int,
    source_type: str,
    attempt_count: int,
    total_count: int,
    correct_count: int,
    duration_seconds: int,
    completed_at: datetime,
    target_accuracy: Decimal,
    benchmark_seconds: Decimal | None,
) -> StudyUserCategoryProfile:
    """
    按贡献值更新用户分类画像

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param category_id: 分类 ID
    :param source_type: 来源类型
    :param attempt_count: 练习次数增量
    :param total_count: 总题数增量
    :param correct_count: 正确题数增量
    :param duration_seconds: 耗时秒增量
    :param completed_at: 完成时间
    :param target_accuracy: 目标正确率
    :param benchmark_seconds: 速度基准秒
    :return:
    """
    profile = await study_user_category_profile_dao.get_by_user_category_source(
        db,
        user_id,
        category_id,
        source_type,
    )
    if profile is None:
        profile = StudyUserCategoryProfile(
            user_id=user_id,
            category_id=category_id,
            source_type=source_type,
        )
        db.add(profile)
        await db.flush()

    profile.attempt_count += max(0, attempt_count)
    profile.total_count += max(0, total_count)
    profile.correct_count += max(0, correct_count)
    profile.duration_seconds += max(0, duration_seconds)
    profile.last_attempt_at = completed_at
    profile.algorithm_version = ALGORITHM_VERSION

    _refresh_profile_scores(profile, target_accuracy, benchmark_seconds)
    return profile


def _refresh_profile_scores(
    profile: StudyUserCategoryProfile,
    target_accuracy: Decimal,
    benchmark_seconds: Decimal | None,
) -> None:
    """
    刷新画像分数

    :param profile: 用户分类画像
    :param target_accuracy: 目标正确率
    :param benchmark_seconds: 速度基准秒
    :return:
    """
    if profile.total_count <= 0:
        profile.accuracy_rate = Decimal('0')
        profile.avg_seconds = None
        profile.mastery_score = Decimal('0')
        profile.speed_score = Decimal('0')
        profile.confidence_score = Decimal('0')
        profile.trend_score = Decimal('0')
        profile.weakness_score = Decimal('100')
        return

    accuracy_ratio = Decimal(profile.correct_count) / Decimal(profile.total_count)
    accuracy_rate = accuracy_ratio * Decimal('100')
    avg_seconds = Decimal(profile.duration_seconds) / Decimal(profile.total_count)
    confidence_score = Decimal(str((1 - exp(-profile.total_count / 30)) * 100))
    accuracy_score = _clamp_score(accuracy_ratio / target_accuracy * Decimal('100'))
    speed_score = _resolve_speed_score(avg_seconds, benchmark_seconds, accuracy_score)
    mastery_score = (
        accuracy_score * Decimal('0.75') + speed_score * Decimal('0.15') + confidence_score * Decimal('0.10')
    )
    mastery_score = _clamp_score(mastery_score)

    profile.accuracy_rate = _to_decimal(accuracy_rate, '0.01') or Decimal('0')
    profile.avg_seconds = _to_decimal(avg_seconds, '0.01')
    profile.mastery_score = _to_decimal(mastery_score, '0.01') or Decimal('0')
    profile.speed_score = _to_decimal(speed_score, '0.01') or Decimal('0')
    profile.confidence_score = _to_decimal(confidence_score, '0.01') or Decimal('0')
    profile.trend_score = Decimal('0')
    profile.weakness_score = _to_decimal(Decimal('100') - mastery_score, '0.01') or Decimal('0')


def _resolve_speed_score(
    avg_seconds: Decimal,
    benchmark_seconds: Decimal | None,
    fallback_score: Decimal,
) -> Decimal:
    """
    计算速度分

    :param avg_seconds: 平均耗时秒
    :param benchmark_seconds: 速度基准秒
    :param fallback_score: 兜底分数
    :return:
    """
    if benchmark_seconds is None:
        return fallback_score
    if avg_seconds <= 0:
        return Decimal('100')
    return _clamp_score(benchmark_seconds / avg_seconds * Decimal('100'))


def _build_profile_detail(
    profile: StudyUserCategoryProfile,
    category: Category | None,
) -> GetStudyUserCategoryProfileDetail:
    """
    构建画像详情

    :param profile: 用户分类画像
    :param category: 分类
    :return:
    """
    return GetStudyUserCategoryProfileDetail(
        id=profile.id,
        user_id=profile.user_id,
        category_id=profile.category_id,
        category_name=category.name if category is not None else None,
        category_code=category.code if category is not None else None,
        category_type=category.type if category is not None else None,
        source_type=profile.source_type,
        attempt_count=profile.attempt_count,
        total_count=profile.total_count,
        correct_count=profile.correct_count,
        duration_seconds=profile.duration_seconds,
        accuracy_rate=float(profile.accuracy_rate),
        avg_seconds=float(profile.avg_seconds) if profile.avg_seconds is not None else None,
        mastery_score=float(profile.mastery_score),
        speed_score=float(profile.speed_score),
        confidence_score=float(profile.confidence_score),
        trend_score=float(profile.trend_score),
        weakness_score=float(profile.weakness_score),
        last_attempt_at=profile.last_attempt_at,
        algorithm_version=profile.algorithm_version,
        updated_time=profile.updated_time,
    )


def _weighted_int(value: int, weight: Decimal) -> int:
    """
    计算加权整数

    :param value: 原始值
    :param weight: 权重
    :return:
    """
    if value <= 0:
        return 0
    result = (Decimal(value) * weight).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    parsed = int(result)
    if parsed <= 0:
        return 1
    return parsed


def _score_to_int(score: Decimal | None) -> int | None:
    """
    标准化分数转整数

    :param score: 标准化分数
    :return:
    """
    if score is None:
        return None
    return int(score.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _clamp_score(score: Decimal) -> Decimal:
    """
    限制分数范围

    :param score: 原始分数
    :return:
    """
    if score < 0:
        return Decimal('0')
    if score > 100:
        return Decimal('100')
    return score


def _to_decimal(value: Any, quant: str) -> Decimal | None:
    """
    转换 Decimal

    :param value: 原始值
    :param quant: 量化精度
    :return:
    """
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal(quant), rounding=ROUND_HALF_UP)
