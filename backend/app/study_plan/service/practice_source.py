#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.schema.question import QuestionCollectParam
from backend.app.question_bank.service.question_selector_service import question_selector_service
from backend.app.question_bank.service.session_service import session_service
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


def _build_collect_param(param: PreviewStudyPlanPracticeSourceParam) -> QuestionCollectParam:
    """
    构建统一筛题参数

    :param param: 预览参数
    :return:
    """
    question_ids = param.question_ids if param.source_mode == 'question_ids' else None
    knowledge_points = param.knowledge_points if param.source_mode == 'knowledge_point' else None
    question_types = param.question_types if param.source_mode == 'chapter_type' else None

    return QuestionCollectParam(
        source_type='placement',
        question_ids=question_ids,
        bank_id=param.bank_id,
        chapter_id=param.chapter_id,
        cat_id=param.cat_id,
        year_start=param.year_start,
        year_end=param.year_end,
        region=param.region,
        knowledge_point=knowledge_points,
        question_types=question_types,
        content_status=10,
        is_active=True,
    )


async def preview_practice_source(
    db: AsyncSession,
    param: PreviewStudyPlanPracticeSourceParam,
) -> PreviewStudyPlanPracticeSourceResult:
    """
    预览刷题来源可用题量

    :param db: 数据库会话
    :param param: 预览参数
    :return:
    """
    _validate_practice_source(param)
    collect_param = _build_collect_param(param)
    bank_scope_ids = await session_service._resolve_placement_bank_scope(
        db=db,
        bank_id=param.bank_id,
    )
    if param.bank_id is not None:
        collect_param.cat_id = None
    if bank_scope_ids and param.bank_id is not None and param.bank_id not in bank_scope_ids:
        collect_param.bank_ids = bank_scope_ids

    collect_result = await question_selector_service.collect_question_ids(
        db=db,
        params=collect_param,
    )
    requested_count = param.question_count or collect_result.total
    selected_count = min(requested_count, collect_result.total)

    return PreviewStudyPlanPracticeSourceResult(
        available_count=collect_result.total,
        selected_count=selected_count,
        sample_question_ids=collect_result.question_ids[:20],
    )
