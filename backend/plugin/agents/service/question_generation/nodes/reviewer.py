#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.question_generation.nodes.candidate_utils import normalize_candidate_passages
from backend.plugin.agents.service.question_generation.outputs import GeneratedQuestionOutput, QuestionReviewOutput

MAX_QUESTION_REPAIR_ROUNDS = 2


async def review_generation(ctx: NodeContext) -> None:
    """质检并修复候选题"""
    state = ctx.state
    if not state.candidates:
        state.qc = {
            'passed': False,
            'confidence': 0,
            'notes': ['无候选题可质检'],
            'rejected_indices': [],
        }
        return

    pending_candidates = state.candidates
    passed_candidates: list[dict[str, Any]] = []
    discarded_candidates: list[dict[str, Any]] = []
    question_reviews: list[dict[str, Any]] = []

    for round_index in range(MAX_QUESTION_REPAIR_ROUNDS + 1):
        review_output = await _invoke_question_review(ctx, pending_candidates, round_index)
        review_items = [item.model_dump(mode='json') for item in review_output.items]
        question_reviews.extend(review_items)
        review_map = {
            int(item.get('candidate_index') or 0): item
            for item in review_items
        }

        revise_candidates: list[dict[str, Any]] = []
        for index, candidate in enumerate(pending_candidates):
            review = review_map.get(index)
            if review is None:
                discarded_candidates.append({**candidate, 'discard_reason': '成题质检缺失'})
                continue
            candidate_with_review = dict(candidate)
            candidate_with_review['question_review'] = review
            decision = str(review.get('decision') or '')
            if decision == 'pass':
                passed_candidates.append(candidate_with_review)
                continue
            if decision == 'revise' and round_index < MAX_QUESTION_REPAIR_ROUNDS:
                revise_candidates.append(candidate_with_review)
                continue
            discarded_candidates.append({
                **candidate_with_review,
                'discard_reason': review.get('reason') or '成题质检未通过',
            })

        if not revise_candidates:
            break

        revision_output = await _invoke_question_revision(ctx, revise_candidates)
        pending_candidates = normalize_candidate_passages(
            state,
            [item.model_dump(mode='json') for item in revision_output.items],
        )

    state.candidates = passed_candidates
    state.question_reviews = question_reviews
    state.discarded_candidates = discarded_candidates
    state.qc = {
        'passed': bool(passed_candidates),
        'confidence': 0.9 if passed_candidates else 0,
        'notes': [
            f'通过候选题 {len(passed_candidates)} 道',
            f'舍弃候选题 {len(discarded_candidates)} 道',
        ],
        'rejected_indices': [],
        'question_reviews': question_reviews,
        'discarded_candidates': discarded_candidates,
    }


async def _invoke_question_review(
    ctx: NodeContext,
    candidates: list[dict[str, Any]],
    round_index: int,
) -> QuestionReviewOutput:
    """
    调用成题质检

    :param ctx: 节点上下文
    :param candidates: 候选题
    :param round_index: 轮次
    :return:
    """
    state = ctx.state
    system, user, _ = ctx.prompts.load_and_render(
        'question_reviewer',
        {
            'profile': state.profile,
            'material_content': state.material_content,
            'selected_passages': state.selected_passages,
            'passage_plan': state.passage_plan,
            'question_type_opportunities': state.question_type_opportunities,
            'blueprints': state.blueprints,
            'candidates': candidates,
            'round_index': round_index,
        },
    )
    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=QuestionReviewOutput,
        temperature=0.0,
        max_tokens=8192,
    )
    ctx.last_llm_stats = stats
    return output


async def _invoke_question_revision(
    ctx: NodeContext,
    candidates: list[dict[str, Any]],
) -> GeneratedQuestionOutput:
    """
    调用候选题修复

    :param ctx: 节点上下文
    :param candidates: 待修候选题
    :return:
    """
    state = ctx.state
    system, user, _ = ctx.prompts.load_and_render(
        'question_reviser',
        {
            'profile': state.profile,
            'material_content': state.material_content,
            'selected_passages': state.selected_passages,
            'question_type_opportunities': state.question_type_opportunities,
            'blueprints': state.blueprints,
            'candidates': candidates,
        },
    )
    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=GeneratedQuestionOutput,
        temperature=0.2,
        max_tokens=12000,
    )
    ctx.last_llm_stats = stats
    return output
