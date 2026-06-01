#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.agents.schema import KeyPointItem, PointSource
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.shenlun.outputs import AnswerAnalyzerOutput


async def analyze_answer(ctx: NodeContext) -> None:
    """考生答案要点抽取"""
    if ctx.state.key_points is None or not ctx.state.user_answer_text.strip():
        return

    system, user, _ = ctx.prompts.load_and_render(
        'answer_analyzer',
        {
            'question': ctx.state.question,
            'user_answer_text': ctx.state.user_answer_text,
        },
    )

    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=AnswerAnalyzerOutput,
        temperature=0.2,
        max_tokens=8192,
    )
    ctx.last_llm_stats = stats

    ctx.state.key_points.answer_points = [
        KeyPointItem(
            text=p.text,
            source=PointSource.answer,
            matched_user_text=p.original_excerpt or None,
            weight=p.weight,
        )
        for p in output.points
    ]
