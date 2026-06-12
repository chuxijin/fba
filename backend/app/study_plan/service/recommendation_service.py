#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dataclasses import dataclass
from datetime import datetime
from math import ceil

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.study_plan.model.ability_profile import StudyAbilityCategoryBinding
from backend.app.study_plan.schema.ability import GetStudyPlanAbilityCatalogItem, GetStudyUserCategoryProfileDetail
from backend.app.study_plan.schema.recommendation import (
    GetStudyPlanItemRecommendation,
    RecommendationModuleType,
    StudyPlanItemRecommendationDraft,
)
from backend.app.study_plan.service.ability_catalog import list_ability_catalog_with_db
from backend.app.study_plan.service.ability_profile import list_user_category_profiles
from backend.utils.timezone import timezone

STRATEGY = 'profile_rule_engine'
STRATEGY_VERSION = 'profile_rule_v1'
DEFAULT_PRACTICE_SECONDS = 90


@dataclass(slots=True)
class ProfileAggregate:
    """画像聚合项"""

    category_id: int
    category_name: str | None
    category_code: str | None
    category_type: str | None
    source_types: list[str]
    total_count: int
    correct_count: int
    duration_seconds: int
    attempt_count: int
    mastery_score: float
    weakness_score: float
    accuracy_rate: float
    speed_score: float
    confidence_score: float
    last_attempt_at: datetime | None


async def list_plan_item_recommendations(
    db: AsyncSession,
    user_id: int,
    *,
    source_type: str | None = None,
    category_id: int | None = None,
    include_children: bool = True,
    module_type: RecommendationModuleType | None = None,
    limit: int = 10,
) -> list[GetStudyPlanItemRecommendation]:
    """
    获取画像驱动计划项推荐

    :param db: 数据库会话
    :param user_id: 学员用户 ID
    :param source_type: 画像来源
    :param category_id: 分类 ID
    :param include_children: 是否包含子孙分类
    :param module_type: 推荐模块类型
    :param limit: 返回数量
    :return:
    """
    profiles = await list_user_category_profiles(
        db,
        user_id,
        source_type,
        category_id,
        include_children,
    )
    aggregates = _aggregate_profiles(profiles)
    if not aggregates:
        return []

    catalog_map = await _list_catalog_map(db)
    bindings_map = await _list_bindings_map(db, [item.category_id for item in aggregates])

    recommendations: list[GetStudyPlanItemRecommendation] = []
    for profile in aggregates:
        if _should_recommend_practice(profile, module_type):
            recommendations.append(_build_practice_recommendation(profile))

        if _should_recommend_ability(profile, module_type):
            ability = _select_ability_for_category(profile, bindings_map, catalog_map)
            if ability is not None:
                recommendations.append(_build_ability_recommendation(profile, ability))

    return sorted(
        recommendations,
        key=lambda item: item.priority_score,
        reverse=True,
    )[: max(1, min(limit, 50))]


def _aggregate_profiles(profiles: list[GetStudyUserCategoryProfileDetail]) -> list[ProfileAggregate]:
    """
    聚合多来源分类画像

    :param profiles: 原始画像
    :return:
    """
    grouped: dict[int, list[GetStudyUserCategoryProfileDetail]] = {}
    for profile in profiles:
        if profile.total_count <= 0:
            continue
        group = grouped.get(profile.category_id) or []
        group.append(profile)
        grouped[profile.category_id] = group

    aggregates = [_build_profile_aggregate(group) for group in grouped.values()]
    return [
        item for item in aggregates
        if item.mastery_score < 78 or item.weakness_score > 25
    ]


def _build_profile_aggregate(group: list[GetStudyUserCategoryProfileDetail]) -> ProfileAggregate:
    """
    构建画像聚合项

    :param group: 同分类画像
    :return:
    """
    base = group[0]
    total_count = sum(item.total_count for item in group)
    correct_count = sum(item.correct_count for item in group)
    duration_seconds = sum(item.duration_seconds for item in group)
    attempt_count = sum(item.attempt_count for item in group)
    mastery_score = _weighted_average(group, 'mastery_score')
    weakness_score = max(0, 100 - mastery_score)
    latest_time = _latest_time([item.last_attempt_at for item in group])

    return ProfileAggregate(
        category_id=base.category_id,
        category_name=base.category_name,
        category_code=base.category_code,
        category_type=base.category_type,
        source_types=sorted({item.source_type for item in group}),
        total_count=total_count,
        correct_count=correct_count,
        duration_seconds=duration_seconds,
        attempt_count=attempt_count,
        mastery_score=mastery_score,
        weakness_score=weakness_score,
        accuracy_rate=(correct_count * 100 / total_count) if total_count else 0,
        speed_score=_weighted_average(group, 'speed_score'),
        confidence_score=_weighted_average(group, 'confidence_score'),
        last_attempt_at=latest_time,
    )


async def _list_catalog_map(db: AsyncSession) -> dict[str, GetStudyPlanAbilityCatalogItem]:
    """获取能力目录映射"""
    catalog = await list_ability_catalog_with_db(
        db,
        domain='civil_service',
        include_inactive=False,
    )
    return {
        item.key: item
        for item in catalog
        if item.supports_study_plan
    }


async def _list_bindings_map(
    db: AsyncSession,
    category_ids: list[int],
) -> dict[int, list[StudyAbilityCategoryBinding]]:
    """
    获取分类绑定映射

    :param db: 数据库会话
    :param category_ids: 分类 ID 列表
    :return:
    """
    ids = sorted(set(category_ids))
    if not ids:
        return {}

    stmt = (
        select(StudyAbilityCategoryBinding)
        .where(
            StudyAbilityCategoryBinding.category_id.in_(ids),
            StudyAbilityCategoryBinding.deleted == 0,
        )
        .order_by(
            StudyAbilityCategoryBinding.category_id.asc(),
            StudyAbilityCategoryBinding.is_primary.desc(),
            StudyAbilityCategoryBinding.weight.desc(),
            StudyAbilityCategoryBinding.confidence.desc(),
            StudyAbilityCategoryBinding.id.asc(),
        )
    )
    result = await db.execute(stmt)
    bindings_map: dict[int, list[StudyAbilityCategoryBinding]] = {}
    for binding in result.scalars().all():
        items = bindings_map.get(binding.category_id) or []
        items.append(binding)
        bindings_map[binding.category_id] = items
    return bindings_map


def _select_ability_for_category(
    profile: ProfileAggregate,
    bindings_map: dict[int, list[StudyAbilityCategoryBinding]],
    catalog_map: dict[str, GetStudyPlanAbilityCatalogItem],
) -> GetStudyPlanAbilityCatalogItem | None:
    """
    选择分类对应能力练习

    :param profile: 画像聚合项
    :param bindings_map: 绑定映射
    :param catalog_map: 目录映射
    :return:
    """
    for binding in bindings_map.get(profile.category_id, []):
        catalog = catalog_map.get(binding.ability_key)
        if catalog is not None:
            return catalog
    return None


def _should_recommend_practice(
    profile: ProfileAggregate,
    module_type: RecommendationModuleType | None,
) -> bool:
    """
    判断是否推荐刷题

    :param profile: 画像聚合项
    :param module_type: 推荐模块类型
    :return:
    """
    if module_type is not None and module_type != 'practice':
        return False
    return profile.category_type == 'knowledge_point'


def _should_recommend_ability(
    profile: ProfileAggregate,
    module_type: RecommendationModuleType | None,
) -> bool:
    """
    判断是否推荐能力练习

    :param profile: 画像聚合项
    :param module_type: 推荐模块类型
    :return:
    """
    if module_type is not None and module_type != 'ability':
        return False
    return True


def _build_practice_recommendation(profile: ProfileAggregate) -> GetStudyPlanItemRecommendation:
    """
    构建刷题推荐

    :param profile: 画像聚合项
    :return:
    """
    target_count, target_accuracy = _resolve_targets(profile)
    expected_minutes = _estimate_minutes(profile, target_count)
    extra = {
        'source_mode': 'knowledge_point',
        'source_label': f'知识点 {profile.category_name or profile.category_id}',
        'knowledge_points': [
            {
                'id': profile.category_id,
                'name': profile.category_name or str(profile.category_id),
            }
        ],
        'question_count': target_count,
        'required_accuracy': target_accuracy,
        'shuffle': True,
        'practice_mode': 'practice',
        'recommendation': _build_recommendation_payload(profile, 'practice'),
    }

    return GetStudyPlanItemRecommendation(
        recommendation_key=f'practice:{profile.category_id}:{STRATEGY_VERSION}',
        strategy=STRATEGY,
        strategy_version=STRATEGY_VERSION,
        module_type='practice',
        category_id=profile.category_id,
        category_name=profile.category_name,
        category_code=profile.category_code,
        category_type=profile.category_type,
        source_types=profile.source_types,
        priority_score=_priority_score(profile),
        mastery_score=profile.mastery_score,
        weakness_score=profile.weakness_score,
        accuracy_rate=profile.accuracy_rate,
        speed_score=profile.speed_score,
        confidence_score=profile.confidence_score,
        total_count=profile.total_count,
        reason=_build_reason(profile),
        reason_codes=_build_reason_codes(profile, ['knowledge_point_practice']),
        target_question_count=target_count,
        target_accuracy=target_accuracy,
        item=StudyPlanItemRecommendationDraft(
            module_type='practice',
            title=f'刷题强化：{profile.category_name or profile.category_id}',
            ref_type='question_set',
            ref_id=None,
            expected_minutes=expected_minutes,
            extra=extra,
        ),
        payload=_build_recommendation_payload(profile, 'practice'),
    )


def _build_ability_recommendation(
    profile: ProfileAggregate,
    catalog: GetStudyPlanAbilityCatalogItem,
) -> GetStudyPlanItemRecommendation:
    """
    构建能力练习推荐

    :param profile: 画像聚合项
    :param catalog: 能力目录
    :return:
    """
    target_count, target_accuracy = _resolve_targets(profile)
    target_count = catalog.default_question_count or target_count
    target_accuracy = catalog.default_accuracy or target_accuracy
    expected_minutes = catalog.default_minutes or _estimate_minutes(profile, target_count)
    extra = {
        'ability_key': catalog.key,
        'ability_title': catalog.title,
        'ability_url': catalog.url,
        'question_count': target_count,
        'required_accuracy': target_accuracy,
        'recommendation': _build_recommendation_payload(profile, 'ability'),
    }

    return GetStudyPlanItemRecommendation(
        recommendation_key=f'ability:{catalog.key}:{profile.category_id}:{STRATEGY_VERSION}',
        strategy=STRATEGY,
        strategy_version=STRATEGY_VERSION,
        module_type='ability',
        category_id=profile.category_id,
        category_name=profile.category_name,
        category_code=profile.category_code,
        category_type=profile.category_type,
        source_types=profile.source_types,
        priority_score=_priority_score(profile) + 2,
        mastery_score=profile.mastery_score,
        weakness_score=profile.weakness_score,
        accuracy_rate=profile.accuracy_rate,
        speed_score=profile.speed_score,
        confidence_score=profile.confidence_score,
        total_count=profile.total_count,
        reason=_build_reason(profile),
        reason_codes=_build_reason_codes(profile, ['ability_binding_available']),
        target_question_count=target_count,
        target_accuracy=target_accuracy,
        item=StudyPlanItemRecommendationDraft(
            module_type='ability',
            title=f'能力强化：{catalog.title}',
            ref_type='ability_task',
            ref_id=None,
            expected_minutes=expected_minutes,
            extra=extra,
        ),
        payload=_build_recommendation_payload(profile, 'ability', {'ability_key': catalog.key}),
    )


def _resolve_targets(profile: ProfileAggregate) -> tuple[int, float]:
    """
    解析推荐目标

    :param profile: 画像聚合项
    :return:
    """
    if profile.mastery_score < 40:
        return 30, 0.75
    if profile.mastery_score < 60:
        return 20, 0.8
    return 12, 0.85


def _estimate_minutes(profile: ProfileAggregate, target_count: int) -> int:
    """
    估算预计分钟

    :param profile: 画像聚合项
    :param target_count: 目标题量
    :return:
    """
    avg_seconds = DEFAULT_PRACTICE_SECONDS
    if profile.total_count > 0 and profile.duration_seconds > 0:
        avg_seconds = max(30, int(profile.duration_seconds / profile.total_count))
    return max(10, ceil(target_count * avg_seconds / 60))


def _priority_score(profile: ProfileAggregate) -> float:
    """
    计算推荐优先级

    :param profile: 画像聚合项
    :return:
    """
    accuracy_gap = max(0, 75 - profile.accuracy_rate) / 75 * 100
    speed_gap = max(0, 70 - profile.speed_score) / 70 * 100
    recency_gap = _recency_gap_score(profile.last_attempt_at)
    score = (
        profile.weakness_score * 0.45
        + accuracy_gap * 0.25
        + speed_gap * 0.15
        + profile.confidence_score * 0.10
        + recency_gap * 0.05
    )
    return round(max(0, min(100, score)), 2)


def _build_reason(profile: ProfileAggregate) -> str:
    """
    构建推荐原因

    :param profile: 画像聚合项
    :return:
    """
    return (
        f'掌握度 {profile.mastery_score:.1f}%，'
        f'正确率 {profile.accuracy_rate:.1f}%，'
        f'速度分 {profile.speed_score:.1f}，'
        f'累计 {profile.total_count} 题'
    )


def _build_reason_codes(profile: ProfileAggregate, extra_codes: list[str]) -> list[str]:
    """
    构建推荐原因码

    :param profile: 画像聚合项
    :param extra_codes: 额外原因码
    :return:
    """
    codes: list[str] = []
    if profile.mastery_score < 40:
        codes.append('very_weak_mastery')
    elif profile.mastery_score < 60:
        codes.append('weak_mastery')
    elif profile.mastery_score < 78:
        codes.append('needs_consolidation')
    if profile.accuracy_rate < 65:
        codes.append('low_accuracy')
    if profile.speed_score < 65:
        codes.append('slow_speed')
    if profile.total_count < 10:
        codes.append('low_sample')
    else:
        codes.append('stable_sample')
    codes.extend(extra_codes)
    return codes


def _build_recommendation_payload(
    profile: ProfileAggregate,
    recommendation_type: RecommendationModuleType,
    extra: dict[str, str] | None = None,
) -> dict[str, object]:
    """
    构建推荐扩展载荷

    :param profile: 画像聚合项
    :param recommendation_type: 推荐类型
    :param extra: 额外信息
    :return:
    """
    payload: dict[str, object] = {
        'category_id': profile.category_id,
        'category_type': profile.category_type,
        'recommendation_type': recommendation_type,
        'strategy': STRATEGY,
        'strategy_version': STRATEGY_VERSION,
        'weights': {
            'weakness': 0.45,
            'accuracy_gap': 0.25,
            'speed_gap': 0.15,
            'confidence': 0.10,
            'recency': 0.05,
        },
    }
    if extra:
        payload.update(extra)
    return payload


def _weighted_average(profiles: list[GetStudyUserCategoryProfileDetail], field: str) -> float:
    """
    加权平均

    :param profiles: 画像列表
    :param field: 字段名
    :return:
    """
    total_weight = sum(max(1, item.total_count) for item in profiles)
    if total_weight <= 0:
        return 0
    value = sum(float(getattr(item, field, 0) or 0) * max(1, item.total_count) for item in profiles)
    return round(value / total_weight, 2)


def _latest_time(values: list[datetime | None]) -> datetime | None:
    """
    获取最新时间

    :param values: 时间列表
    :return:
    """
    valid_values = [item for item in values if item is not None]
    if not valid_values:
        return None
    return max(valid_values)


def _recency_gap_score(last_attempt_at: datetime | None) -> float:
    """
    计算久未练习分

    :param last_attempt_at: 最近练习时间
    :return:
    """
    if last_attempt_at is None:
        return 100
    days = (timezone.now() - timezone.from_datetime(last_attempt_at)).days
    return max(0, min(100, days / 30 * 100))
