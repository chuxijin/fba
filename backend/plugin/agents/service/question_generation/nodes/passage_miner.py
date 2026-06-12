#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from backend.common.exception import errors
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.question_generation.outputs import PassageMiningOutput


async def mine_passages(ctx: NodeContext) -> None:
    """挖掘多个命题片段"""
    state = ctx.state
    if state.passage_plan and state.selected_passages:
        return

    output = await _invoke_passage_mining(ctx)
    passage_plan = output.model_dump(mode='json')
    if not output.can_generate or not passage_plan.get('passages'):
        message = output.rejected_reason or 'AI 未从文章中选出适合国考言语命题的连续片段'
        raise errors.RequestError(msg=message)

    state.selected_passages = _normalize_passage_lengths(passage_plan.get('passages') or [])
    passage_plan['passages'] = state.selected_passages
    passage_plan['can_generate'] = True
    state.passage_plan = passage_plan

    question_types: list[str] = []
    question_count = 0
    for passage in state.selected_passages:
        selected_types = passage.get('auto_selected_question_types') or passage.get('recommended_types') or []
        question_types.extend(selected_types)
        question_count += int(passage.get('recommended_question_count') or 1)
    state.target_question_types = list(dict.fromkeys(question_types))
    state.question_count = max(question_count, 1)


async def _invoke_passage_mining(ctx: NodeContext) -> PassageMiningOutput:
    """
    调用 AI 进行选段

    :param ctx: 节点上下文
    :return:
    """
    state = ctx.state
    system, user, _ = ctx.prompts.load_and_render(
        'passage_miner',
        {
            'profile': state.profile,
            'material_title': state.material_title,
            'material_content': state.material_content,
            'article_analysis': state.article_analysis,
        },
    )
    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=PassageMiningOutput,
        temperature=0.15,
        max_tokens=12000,
    )
    ctx.last_llm_stats = stats
    return output


def _normalize_passage_lengths(passages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    规范片段字数字段

    :param passages: 片段列表
    :return:
    """
    normalized_passages: list[dict[str, Any]] = []
    for passage in passages:
        selected_passage = str(passage.get('selected_passage') or '')
        if selected_passage:
            passage['selected_passage_length'] = _count_passage_chars(selected_passage)
        normalized_passages.append(passage)
    return normalized_passages


def _count_passage_chars(text: str) -> int:
    """
    统计片段字数

    :param text: 片段文本
    :return:
    """
    return len(''.join(text.split()))
