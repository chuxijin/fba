#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from backend.common.exception import errors
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.question_generation.outputs import TypeReviewOutput


async def review_question_types(ctx: NodeContext) -> None:
    """质检题型机会"""
    state = ctx.state
    if state.type_reviews and state.question_type_opportunities:
        return

    system, user, _ = ctx.prompts.load_and_render(
        'type_reviewer',
        {
            'profile': state.profile,
            'selected_passages': state.selected_passages,
            'question_type_opportunities': state.question_type_opportunities,
        },
    )
    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=TypeReviewOutput,
        temperature=0.0,
        max_tokens=10000,
    )
    ctx.last_llm_stats = stats
    review_items = [item.model_dump(mode='json') for item in output.items]
    state.type_reviews = review_items

    passed, discarded = _apply_type_reviews(state.question_type_opportunities, review_items)
    if not passed:
        raise errors.RequestError(msg='题型机会未通过质检，无法出题')

    state.question_type_opportunities = passed
    state.discarded_type_opportunities = discarded
    state.target_question_types = list(dict.fromkeys([item['question_type'] for item in passed]))
    state.question_count = len(passed)


def _apply_type_reviews(
    opportunities: list[dict[str, Any]],
    review_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    应用题型质检结果

    :param opportunities: 题型机会
    :param review_items: 质检项
    :return:
    """
    review_map = {
        (str(item.get('passage_id')), str(item.get('question_type'))): item
        for item in review_items
    }
    passed: list[dict[str, Any]] = []
    discarded: list[dict[str, Any]] = []
    for opportunity in opportunities:
        key = (str(opportunity.get('passage_id')), str(opportunity.get('question_type')))
        review = review_map.get(key)
        if review is None:
            discarded.append({**opportunity, 'discard_reason': '题型质检缺失'})
            continue

        decision = str(review.get('decision') or '')
        if decision == 'pass':
            opportunity['type_review'] = review
            passed.append(opportunity)
            continue

        if decision == 'revise' and review.get('repaired_question_type'):
            repaired = dict(opportunity)
            repaired['question_type'] = str(review.get('repaired_question_type'))
            repaired['type_review'] = review
            passed.append(repaired)
            continue

        discarded.append({**opportunity, 'discard_reason': review.get('reason') or '题型质检未通过'})
    return passed, discarded
