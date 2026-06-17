#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from backend.common.exception import errors
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.question_generation.outputs import PassageReviewOutput, PassageRevisionOutput

MAX_PASSAGE_REPAIR_ROUNDS = 2


async def review_passages(ctx: NodeContext) -> None:
    """质检并修复片段"""
    state = ctx.state
    if state.passage_reviews and state.selected_passages:
        return

    passages = state.selected_passages
    review_records: list[dict[str, Any]] = []
    discarded_passages: list[dict[str, Any]] = []
    for round_index in range(MAX_PASSAGE_REPAIR_ROUNDS + 1):
        if not passages:
            break

        review_output = await _invoke_passage_review(ctx, passages, round_index)
        review_items = [item.model_dump(mode='json') for item in review_output.items]
        review_records.extend(review_items)
        decision_map = {str(item.get('passage_id')): item for item in review_items if item.get('passage_id')}

        passed_passages = _collect_passages_by_decision(passages, decision_map, 'pass')
        discard_items = _collect_passages_by_decision(passages, decision_map, 'discard')
        discarded_passages.extend(discard_items)

        revise_passages = _collect_passages_by_decision(passages, decision_map, 'revise')
        if not revise_passages or round_index >= MAX_PASSAGE_REPAIR_ROUNDS:
            discarded_passages.extend(revise_passages)
            passages = passed_passages
            break

        revision_output = await _invoke_passage_revision(ctx, revise_passages, decision_map)
        repaired_passages = _apply_passage_revisions(revise_passages, revision_output.model_dump(mode='json'))
        passages = passed_passages + repaired_passages

    if not passages:
        raise errors.RequestError(msg='候选片段未通过质检，无法进入题型判断')

    state.selected_passages = passages
    state.passage_reviews = review_records
    state.discarded_passages = discarded_passages
    if state.passage_plan:
        state.passage_plan['passages'] = passages
        state.passage_plan['discarded_passages'] = discarded_passages
        state.passage_plan['passage_reviews'] = review_records


async def _invoke_passage_review(
    ctx: NodeContext,
    passages: list[dict[str, Any]],
    round_index: int,
) -> PassageReviewOutput:
    """
    调用片段质检

    :param ctx: 节点上下文
    :param passages: 片段列表
    :param round_index: 轮次
    :return:
    """
    state = ctx.state
    system, user, _ = ctx.prompts.load_and_render(
        'passage_reviewer',
        {
            'profile': state.profile,
            'material_title': state.material_title,
            'material_content': state.material_content,
            'article_analysis': state.article_analysis,
            'passages': passages,
            'round_index': round_index,
        },
    )
    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=PassageReviewOutput,
        temperature=0.0,
        max_tokens=10000,
    )
    ctx.last_llm_stats = stats
    return output


async def _invoke_passage_revision(
    ctx: NodeContext,
    passages: list[dict[str, Any]],
    decision_map: dict[str, dict[str, Any]],
) -> PassageRevisionOutput:
    """
    调用片段修复

    :param ctx: 节点上下文
    :param passages: 片段列表
    :param decision_map: 质检结果
    :return:
    """
    state = ctx.state
    system, user, _ = ctx.prompts.load_and_render(
        'passage_reviser',
        {
            'profile': state.profile,
            'material_title': state.material_title,
            'material_content': state.material_content,
            'article_analysis': state.article_analysis,
            'passages': passages,
            'review_items': decision_map,
        },
    )
    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=PassageRevisionOutput,
        temperature=0.1,
        max_tokens=10000,
    )
    ctx.last_llm_stats = stats
    return output


def _collect_passages_by_decision(
    passages: list[dict[str, Any]],
    decision_map: dict[str, dict[str, Any]],
    decision: str,
) -> list[dict[str, Any]]:
    """
    按质检结论收集片段

    :param passages: 片段列表
    :param decision_map: 质检结果
    :param decision: 目标结论
    :return:
    """
    collected: list[dict[str, Any]] = []
    for passage in passages:
        passage_id = str(passage.get('passage_id') or '')
        item = decision_map.get(passage_id)
        if item is None:
            continue
        if item.get('decision') != decision:
            continue
        passage_copy = dict(passage)
        passage_copy['review_decision'] = item
        collected.append(passage_copy)
    return collected


def _apply_passage_revisions(
    passages: list[dict[str, Any]],
    revision_output: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    应用片段修复结果

    :param passages: 原片段
    :param revision_output: 修复输出
    :return:
    """
    passage_map = {str(item.get('passage_id')): item for item in passages if item.get('passage_id')}
    revised_passages: list[dict[str, Any]] = []
    for revision in revision_output.get('items') or []:
        passage_id = str(revision.get('passage_id') or '')
        original = passage_map.get(passage_id)
        if original is None or not revision.get('can_repair'):
            continue
        revised_selected_passage = str(revision.get('revised_selected_passage') or '').strip()
        if not revised_selected_passage:
            continue

        repaired = dict(original)
        repaired['selected_passage'] = revised_selected_passage
        if revision.get('revised_question_types'):
            repaired['auto_selected_question_types'] = list(revision.get('revised_question_types') or [])
            repaired['recommended_types'] = list(revision.get('revised_question_types') or [])
        repaired['revision_reason'] = revision.get('reason') or ''
        revised_passages.append(repaired)
    return revised_passages
