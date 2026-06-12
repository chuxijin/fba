#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.common.exception import errors
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.question_generation.outputs import BlueprintOutput


async def plan_blueprints(ctx: NodeContext) -> None:
    """规划命题蓝图"""
    state = ctx.state
    if state.blueprints:
        return

    selected_passages = state.selected_passages
    if not selected_passages and state.passage_plan:
        selected_passages = list(state.passage_plan.get('passages') or [])
        state.selected_passages = selected_passages
    if not selected_passages:
        raise errors.RequestError(msg='未找到可用于命题蓝图规划的选段')

    system, user, _ = ctx.prompts.load_and_render(
        'blueprint_planner',
        {
            'profile': state.profile,
            'material_title': state.material_title,
            'material_content': state.material_content,
            'selected_passages': selected_passages,
            'passage_plan': state.passage_plan,
            'question_type_opportunities': state.question_type_opportunities,
            'type_reviews': state.type_reviews,
            'question_count': state.question_count,
        },
    )
    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=BlueprintOutput,
        temperature=0.2,
        max_tokens=8192,
    )
    ctx.last_llm_stats = stats
    state.blueprints = [item.model_dump(mode='json') for item in output.items]
