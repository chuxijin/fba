#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.shenlun.outputs import ClassifierOutput


async def classify(ctx: NodeContext) -> None:
    """题型识别"""
    if ctx.state.question_type:
        return

    system, user, _ = ctx.prompts.load_and_render(
        'classifier',
        {
            'question_stem': ctx.state.question_stem,
            'question': ctx.state.question,
        },
    )

    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.mini,
        system_prompt=system,
        user_prompt=user,
        output_type=ClassifierOutput,
        temperature=0.0,
        max_tokens=8192,
    )
    ctx.last_llm_stats = stats

    ctx.state.question_type = output.question_type
