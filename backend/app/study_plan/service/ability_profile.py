#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from math import exp
from typing import Any

import sqlalchemy as sa

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model.category import Category
from backend.app.question_bank_v2.model.knowledge import QbQuestionKnowledgePoint
from backend.app.question_bank_v2.model.practice import QbPracticeSession, QbQuestionAttempt
from backend.app.study_plan.crud import (
    study_ability_attempt_dao,
    study_ability_catalog_dao,
    study_ability_category_binding_dao,
    study_plan_record_dao,
    study_user_category_profile_dao,
    study_user_knowledge_profile_dao,
)
from backend.app.study_plan.model.ability_profile import (
    StudyAbilityAttempt,
    StudyAbilityAttemptCategory,
    StudyAbilityCategoryBinding,
    StudyUserCategoryProfile,
    StudyUserKnowledgeProfile,
)
from backend.app.study_plan.schema.ability import (
    BatchSubmitStudyAbilityAttemptParam,
    BatchSubmitStudyAbilityAttemptResult,
    GetStudyAbilityAttemptDetail,
    GetStudyAbilityAttemptListItem,
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


@dataclass(slots=True)
class KnowledgePointContribution:
    """题库答题知识点贡献"""

    knowledge_point_id: int
    total_count: int
    correct_count: int
    duration_seconds: int
    completed_at: datetime


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


async def list_user_attempts(
    db: AsyncSession,
    user_id: int,
    ability_key: str | None = None,
    source: str | None = None,
    mode: str | None = None,
    start: date | None = None,
    end: date | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[GetStudyAbilityAttemptListItem], int]:
    """
    获取用户能力练习历史列表

    :param db: 数据库会话
    :param user_id: 学员用户 ID
    :param ability_key: 能力标识过滤
    :param source: 来源过滤
    :param mode: 练习模式过滤
    :param start: 完成日期起始
    :param end: 完成日期截止
    :param offset: 偏移量
    :param limit: 每页数量
    :return:
    """
    rows, total = await study_ability_attempt_dao.list_by_user(
        db,
        user_id=user_id,
        ability_key=ability_key,
        source=source,
        mode=mode,
        start=start,
        end=end,
        offset=offset,
        limit=limit,
    )
    items = [GetStudyAbilityAttemptListItem.model_validate(row) for row in rows]
    return items, total


async def get_user_attempt_detail(
    db: AsyncSession,
    user_id: int,
    client_session_id: str,
) -> GetStudyAbilityAttemptDetail:
    """
    获取单次练习详情（含 records）

    :param db: 数据库会话
    :param user_id: 学员用户 ID
    :param client_session_id: 客户端会话 ID
    :return:
    """
    attempt = await study_ability_attempt_dao.get_by_client_session(db, user_id, client_session_id)
    if attempt is None:
        raise errors.NotFoundError(msg='能力练习记录不存在或无权访问')
    return GetStudyAbilityAttemptDetail.model_validate(attempt)


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
    同步题库 v2 会话答题数据到用户知识点画像

    判分事实取自 QbQuestionAttempt（每题取最新一次提交），知识点走 QbQuestionKnowledgePoint 关联表，
    按 weight 加权分摊到各知识点。题目未标注知识点时返回 0，属正常业务结果。

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param session_id: 题库 v2 会话 ID
    :param completed_at: 完成时间
    :return:
    """
    session = await db.get(QbPracticeSession, session_id)
    if session is None or session.user_id != user_id:
        return 0
    if _is_question_bank_profile_synced(session):
        return 0

    rows = await _list_question_bank_session_rows(db, user_id, session_id)
    if not rows:
        return 0

    profile_completed_at = _resolve_completed_at(completed_at)
    contributions: dict[int, KnowledgePointContribution] = {}
    for row in rows:
        point_id = int(row.knowledge_point_id)
        weight = _to_decimal(row.weight, '0.0001') or Decimal('1')
        # duration_ms 是毫秒且可能为空，画像统一按秒累计
        duration_seconds = max(0, round(int(row.duration_ms or 0) / 1000))
        correct_count = 1 if row.is_correct else 0

        contribution = contributions.get(point_id)
        if contribution is None:
            contributions[point_id] = KnowledgePointContribution(
                knowledge_point_id=point_id,
                total_count=_weighted_int(1, weight),
                correct_count=_weighted_int(correct_count, weight) if correct_count else 0,
                duration_seconds=_weighted_int(duration_seconds, weight) if duration_seconds else 0,
                completed_at=profile_completed_at,
            )
            continue

        contribution.total_count += _weighted_int(1, weight)
        if correct_count:
            contribution.correct_count += _weighted_int(correct_count, weight)
        if duration_seconds:
            contribution.duration_seconds += _weighted_int(duration_seconds, weight)

    if not contributions:
        return 0

    for contribution in contributions.values():
        await _upsert_knowledge_profile(
            db=db,
            user_id=user_id,
            knowledge_point_id=contribution.knowledge_point_id,
            total_count=contribution.total_count,
            correct_count=min(contribution.correct_count, contribution.total_count),
            duration_seconds=contribution.duration_seconds,
            completed_at=contribution.completed_at,
        )

    _mark_question_bank_profile_synced(session, profile_completed_at)
    return len(contributions)


async def _list_question_bank_session_rows(
    db: AsyncSession,
    user_id: int,
    session_id: int,
) -> Sequence[Any]:
    """
    获取题库 v2 会话已判题记录及其知识点关联

    同一投递题可能多次提交，只取每题 attempt_no 最大的那次作为判分事实。

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param session_id: 会话 ID
    :return:
    """
    latest = (
        select(
            QbQuestionAttempt.session_item_id,
            sa.func.max(QbQuestionAttempt.attempt_no).label('attempt_no'),
        )
        .where(
            QbQuestionAttempt.session_id == session_id,
            QbQuestionAttempt.session_item_id.is_not(None),
            QbQuestionAttempt.deleted == 0,
        )
        .group_by(QbQuestionAttempt.session_item_id)
        .subquery()
    )
    stmt = (
        select(
            QbQuestionAttempt.question_id,
            QbQuestionAttempt.is_correct,
            QbQuestionAttempt.duration_ms,
            QbQuestionKnowledgePoint.knowledge_point_id,
            QbQuestionKnowledgePoint.weight,
        )
        .join(
            latest,
            sa.and_(
                latest.c.session_item_id == QbQuestionAttempt.session_item_id,
                latest.c.attempt_no == QbQuestionAttempt.attempt_no,
            ),
        )
        .join(
            QbQuestionKnowledgePoint,
            sa.and_(
                QbQuestionKnowledgePoint.question_id == QbQuestionAttempt.question_id,
                QbQuestionKnowledgePoint.deleted == 0,
            ),
        )
        .where(
            QbQuestionAttempt.session_id == session_id,
            QbQuestionAttempt.user_id == user_id,
            # 主观题待批时 is_correct 为空，不参与画像
            QbQuestionAttempt.is_correct.is_not(None),
            QbQuestionAttempt.deleted == 0,
        )
    )
    result = await db.execute(stmt)
    return result.all()


async def _upsert_knowledge_profile(
    *,
    db: AsyncSession,
    user_id: int,
    knowledge_point_id: int,
    total_count: int,
    correct_count: int,
    duration_seconds: int,
    completed_at: datetime,
) -> StudyUserKnowledgeProfile:
    """
    按贡献值更新用户知识点画像

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param knowledge_point_id: 题库 v2 知识点 ID
    :param total_count: 总题数增量
    :param correct_count: 正确题数增量
    :param duration_seconds: 耗时秒增量
    :param completed_at: 完成时间
    :return:
    """
    profile = await study_user_knowledge_profile_dao.get_by_user_point(db, user_id, knowledge_point_id)
    if profile is None:
        profile = StudyUserKnowledgeProfile(
            user_id=user_id,
            knowledge_point_id=knowledge_point_id,
        )
        db.add(profile)
        await db.flush()

    profile.attempt_count += 1
    profile.total_count += max(0, total_count)
    profile.correct_count += max(0, correct_count)
    profile.duration_seconds += max(0, duration_seconds)
    profile.last_attempt_at = completed_at
    profile.algorithm_version = ALGORITHM_VERSION

    _refresh_profile_scores(profile, DEFAULT_TARGET_ACCURACY, QUESTION_BANK_BENCHMARK_SECONDS)
    return profile


def _is_question_bank_profile_synced(session: QbPracticeSession) -> bool:
    """
    判断题库画像是否已同步

    :param session: 题库 v2 会话
    :return:
    """
    snapshot = session.source_snapshot or {}
    return bool(snapshot.get('question_bank_profile_synced_at'))


def _mark_question_bank_profile_synced(session: QbPracticeSession, completed_at: datetime) -> None:
    """
    标记题库画像已同步

    :param session: 题库 v2 会话
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
    profile: StudyUserCategoryProfile | StudyUserKnowledgeProfile,
    target_accuracy: Decimal,
    benchmark_seconds: Decimal | None,
) -> None:
    """
    刷新画像分数

    :param profile: 用户分类画像或知识点画像
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
