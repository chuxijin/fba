#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from backend.plugin.agents.schema import QuestionGenerationState


def normalize_candidate_passages(
    state: QuestionGenerationState, candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    归一化候选题片段与完整题面

    :param state: 出题状态
    :param candidates: 候选题列表
    :return:
    """
    selected_passages = state.selected_passages
    if not selected_passages and state.passage_plan:
        selected_passages = list(state.passage_plan.get('passages') or [])
        state.selected_passages = selected_passages

    passage_map = {str(item.get('passage_id')): item for item in selected_passages if item.get('passage_id')}
    blueprint_map = {str(item.get('passage_id')): item for item in state.blueprints if item.get('passage_id')}

    for index, candidate in enumerate(candidates):
        passage_id = _resolve_passage_id(candidate, state.blueprints, index)
        if passage_id:
            candidate['passage_id'] = passage_id

        passage_meta = passage_map.get(passage_id)
        blueprint = blueprint_map.get(passage_id)
        selected_passage = _resolve_selected_passage(candidate, passage_meta, blueprint)
        if passage_meta is not None:
            candidate['passage_meta'] = passage_meta
        if selected_passage:
            candidate['selected_passage'] = selected_passage
            candidate['stem'] = _build_full_stem(selected_passage, str(candidate.get('stem') or ''))

    return candidates


def _resolve_passage_id(
    candidate: dict[str, Any],
    blueprints: list[dict[str, Any]],
    index: int,
) -> str:
    """
    解析候选题片段标识

    :param candidate: 候选题
    :param blueprints: 命题蓝图
    :param index: 候选题序号
    :return:
    """
    passage_id = str(candidate.get('passage_id') or '')
    if passage_id:
        return passage_id

    blueprint = candidate.get('blueprint')
    if isinstance(blueprint, dict) and blueprint.get('passage_id'):
        return str(blueprint.get('passage_id'))

    if index < len(blueprints) and blueprints[index].get('passage_id'):
        return str(blueprints[index].get('passage_id'))

    return ''


def _resolve_selected_passage(
    candidate: dict[str, Any],
    passage_meta: dict[str, Any] | None,
    blueprint: dict[str, Any] | None,
) -> str:
    """
    解析候选题命题片段

    :param candidate: 候选题
    :param passage_meta: 片段元信息
    :param blueprint: 命题蓝图
    :return:
    """
    selected_passage = str(candidate.get('selected_passage') or '').strip()
    if selected_passage:
        return selected_passage
    if passage_meta and passage_meta.get('selected_passage'):
        return str(passage_meta.get('selected_passage')).strip()
    if blueprint and blueprint.get('selected_passage'):
        return str(blueprint.get('selected_passage')).strip()
    return ''


def _build_full_stem(selected_passage: str, stem: str) -> str:
    """
    构建包含文段的完整题干

    :param selected_passage: 命题片段
    :param stem: 原题干
    :return:
    """
    selected_passage = selected_passage.strip()
    stem = stem.strip()
    if not selected_passage:
        return stem
    if selected_passage in stem:
        return stem
    if stem and stem[:30] in selected_passage:
        return stem
    if not stem:
        return selected_passage
    return f'{selected_passage}\n\n{stem}'
