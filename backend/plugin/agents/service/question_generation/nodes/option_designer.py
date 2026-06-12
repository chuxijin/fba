#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.question_generation.nodes.candidate_utils import normalize_candidate_passages
from backend.plugin.agents.service.question_generation.outputs import GeneratedQuestionOutput


async def design_options(ctx: NodeContext) -> None:
    """校准选项陷阱"""
    state = ctx.state
    if not state.candidates:
        return
    if state.extras.get('option_design_checked'):
        return

    system, user, _ = ctx.prompts.load_and_render(
        'option_designer',
        {
            'profile': state.profile,
            'material_content': state.material_content,
            'selected_passages': state.selected_passages,
            'passage_plan': state.passage_plan,
            'question_type_opportunities': state.question_type_opportunities,
            'blueprints': state.blueprints,
            'candidates': state.candidates,
        },
    )
    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=GeneratedQuestionOutput,
        temperature=0.15,
        max_tokens=12000,
    )
    ctx.last_llm_stats = stats
    candidates = [item.model_dump(mode='json') for item in output.items]
    state.candidates = normalize_candidate_passages(state, candidates)
    state.extras['option_design_checked'] = True
