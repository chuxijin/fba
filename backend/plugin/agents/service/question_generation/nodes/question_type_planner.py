#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from backend.common.exception import errors
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.question_generation.outputs import QuestionTypePlanningOutput


async def plan_question_types(ctx: NodeContext) -> None:
    """规划片段题型机会"""
    state = ctx.state
    if state.question_type_opportunities:
        return

    system, user, _ = ctx.prompts.load_and_render(
        'question_type_planner',
        {
            'profile': state.profile,
            'material_content': state.material_content,
            'selected_passages': state.selected_passages,
            'passage_reviews': state.passage_reviews,
        },
    )
    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=QuestionTypePlanningOutput,
        temperature=0.1,
        max_tokens=10000,
    )
    ctx.last_llm_stats = stats
    opportunities: list[dict[str, Any]] = []
    for item in output.items:
        opportunity = item.model_dump(mode='json')
        passage_length = int(opportunity.get('selected_passage_length') or 0)
        if passage_length <= 0:
            passage_length = len(''.join(str(opportunity.get('selected_passage') or '').split()))
            opportunity['selected_passage_length'] = passage_length
        opportunities.append(opportunity)
    if not opportunities:
        raise errors.RequestError(msg='AI 未输出可用于出题的题型机会')

    state.question_type_opportunities = opportunities
    state.target_question_types = list(dict.fromkeys([item['question_type'] for item in opportunities]))
    state.question_count = len(opportunities)
