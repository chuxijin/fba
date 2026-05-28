#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Any

import yaml

from backend.plugin.agents.schema import KeyPointsSection
from backend.plugin.agents.service.common.orchestrator import NodeContext

_RUBRIC_FILES: dict[str, str] = {
    '大作文': 'essay.yaml',
    '归纳概括': 'summary.yaml',
    '综合分析': 'analysis.yaml',
    '提出对策': 'countermeasure.yaml',
    '应用文': 'application.yaml',
}

_DEFAULT_RUBRIC: dict[str, Any] = {
    'dimensions': [
        {'name': '立意', 'max_score': 12, 'weight': 0.30},
        {'name': '结构', 'max_score': 8, 'weight': 0.20},
        {'name': '论证', 'max_score': 10, 'weight': 0.25},
        {'name': '文采', 'max_score': 6, 'weight': 0.15},
        {'name': '规范', 'max_score': 4, 'weight': 0.10},
    ],
    'total': 40,
}


async def load_rubric(ctx: NodeContext) -> None:
    """按题型加载评分细则, 初始化下游 section"""
    question_type = ctx.state.question_type or '大作文'
    rubric_file = _RUBRIC_FILES.get(question_type, 'essay.yaml')
    rubric_path = Path(__file__).resolve().parent.parent / 'rubrics' / rubric_file

    if rubric_path.exists():
        ctx.state.rubric = yaml.safe_load(rubric_path.read_text(encoding='utf-8'))
    else:
        ctx.state.rubric = dict(_DEFAULT_RUBRIC)

    original_total = float(ctx.state.rubric.get('total') or 40.0)
    requested_total = ctx.state.score_total
    if requested_total is None:
        ctx.state.score_total = original_total
    else:
        ctx.state.rubric = _scale_rubric_total(ctx.state.rubric, requested_total, original_total)
        ctx.state.score_total = requested_total

    if ctx.state.key_points is None:
        ctx.state.key_points = KeyPointsSection()


def _scale_rubric_total(
    rubric: dict[str, Any],
    requested_total: float,
    original_total: float,
) -> dict[str, Any]:
    """
    按调用方指定总分等比缩放评分维度

    :param rubric: 原始评分细则
    :param requested_total: 调用方指定满分
    :param original_total: 评分细则原始满分
    :return:
    """
    rubric = dict(rubric)
    rubric['total'] = requested_total
    if original_total <= 0 or requested_total <= 0:
        return rubric

    scale = requested_total / original_total
    dimensions = []
    for dimension in rubric.get('dimensions', []):
        dimension_copy = dict(dimension)
        max_score = float(dimension_copy.get('max_score') or 0)
        dimension_copy['max_score'] = round(max_score * scale, 2)
        dimensions.append(dimension_copy)
    rubric['dimensions'] = dimensions
    return rubric
