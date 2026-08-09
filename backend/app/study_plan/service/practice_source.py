#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.schema.question import CollectQuestionsParam
from backend.app.question_bank_v2.service.practice_service import practice_service
from backend.app.study_plan.schema.practice_source import (
    PreviewStudyPlanPracticeSourceParam,
    PreviewStudyPlanPracticeSourceResult,
)
from backend.common.exception import errors


def _has_items(value: list | None) -> bool:
    """
    判断列表是否有有效项

    :param value: 原始列表
    :return:
    """
    return isinstance(value, list) and len(value) > 0


def _validate_practice_source(param: PreviewStudyPlanPracticeSourceParam) -> None:
    """
    校验刷题来源配置

    :param param: 预览参数
    :return:
    """
    if param.source_mode in {'bank', 'chapter', 'chapter_type'} and param.bank_id is None:
        raise errors.RequestError(msg='请选择题库')

    if param.source_mode in {'chapter', 'chapter_type'} and param.chapter_id is None:
        raise errors.RequestError(msg='请选择题库篇章')

    if param.source_mode == 'chapter_type' and not _has_items(param.question_types):
        raise errors.RequestError(msg='请选择题型')

    if param.source_mode == 'knowledge_point' and not _has_items(param.knowledge_points):
        raise errors.RequestError(msg='请选择知识点')

    if param.source_mode == 'question_ids' and not _has_items(param.question_ids):
        raise errors.RequestError(msg='请填写题目 ID')


def resolve_knowledge_point_ids(raw_values: list[Any] | None) -> list[int]:
    """
    解析知识点条件中的题库 v2 知识点 ID

    题库 v2 的知识点是带层级的独立实体，只接受数值 ID；导师手敲的纯名称无法定位到节点，直接忽略。

    :param raw_values: 前端传入的知识点条件，元素可能是 ID、字符串或 {id, name} 结构
    :return:
    """
    point_ids: list[int] = []
    seen: set[int] = set()
    for raw_value in raw_values or []:
        candidate = raw_value.get('id') if isinstance(raw_value, dict) else raw_value
        if isinstance(candidate, bool):
            continue
        if isinstance(candidate, str):
            text = candidate.strip()
            candidate = int(text) if text.isdigit() else None
        if not isinstance(candidate, int) or candidate <= 0 or candidate in seen:
            continue
        seen.add(candidate)
        point_ids.append(candidate)
    return point_ids


def _build_collect_param(param: PreviewStudyPlanPracticeSourceParam) -> CollectQuestionsParam:
    """
    构建题库 v2 统一采集参数

    :param param: 预览参数
    :return:
    """
    if param.source_mode == 'question_ids':
        return CollectQuestionsParam(source_type='custom', question_ids=param.question_ids or [])

    knowledge_point_ids = (
        resolve_knowledge_point_ids(param.knowledge_points) if param.source_mode == 'knowledge_point' else []
    )
    question_types = param.question_types if param.source_mode == 'chapter_type' else None

    return CollectQuestionsParam(
        source_type='bank',
        bank_id=param.bank_id,
        section_id=param.chapter_id,
        knowledge_point_ids=knowledge_point_ids,
        question_types=question_types or [],
        year_start=param.year_start,
        year_end=param.year_end,
        region=param.region,
    )


async def preview_practice_source(
    db: AsyncSession,
    param: PreviewStudyPlanPracticeSourceParam,
    user_id: int,
) -> PreviewStudyPlanPracticeSourceResult:
    """
    预览刷题来源可用题量

    :param db: 数据库会话
    :param param: 预览参数
    :param user_id: 操作者用户 ID，用于题库访问准入校验
    :return:
    """
    _validate_practice_source(param)
    collect_param = _build_collect_param(param)
    if param.source_mode == 'knowledge_point' and not collect_param.knowledge_point_ids:
        raise errors.RequestError(msg='知识点需要从列表中选择，手动填写的名称无法定位题库知识点')

    collect_result = await practice_service.collect_questions(
        db=db,
        user_id=user_id,
        obj=collect_param,
    )
    requested_count = param.question_count or collect_result.total
    selected_count = min(requested_count, collect_result.total)

    return PreviewStudyPlanPracticeSourceResult(
        available_count=collect_result.total,
        selected_count=selected_count,
        sample_question_ids=collect_result.question_ids[:20],
    )
