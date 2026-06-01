#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.agents.schema import ConsensusLevel, KeyPointItem, PointSource
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.shenlun.outputs import ReferenceAnalyzerOutput


async def analyze_reference(ctx: NodeContext) -> None:
    """参考答案聚合"""
    if ctx.state.key_points is None or not ctx.state.reference_answers:
        return

    system, user, _ = ctx.prompts.load_and_render(
        'reference_analyzer',
        {
            'question': ctx.state.question,
            'reference_answers': ctx.state.reference_answers,
            'ref_count': len(ctx.state.reference_answers),
        },
    )

    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=ReferenceAnalyzerOutput,
        temperature=0.1,
        max_tokens=8192,
    )
    ctx.last_llm_stats = stats

    ctx.state.key_points.reference_points = [
        KeyPointItem(
            text=p.text,
            source=PointSource.reference,
            consensus_count=p.consensus_count,
            consensus_level=ConsensusLevel(p.consensus_level),
            weight=p.weight,
        )
        for p in output.points
    ]
