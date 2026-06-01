#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.agents.schema import KeyPointItem, PointSource
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.shenlun.outputs import MaterialParserOutput


async def parse_material(ctx: NodeContext) -> None:
    """材料解析"""
    if ctx.state.key_points is None or not ctx.state.materials.strip():
        return

    system, user, _ = ctx.prompts.load_and_render(
        'material_parser',
        {
            'question': ctx.state.question,
            'materials': ctx.state.materials,
        },
    )

    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=MaterialParserOutput,
        temperature=0.2,
        max_tokens=8192,
    )
    ctx.last_llm_stats = stats

    ctx.state.key_points.material_points = [
        KeyPointItem(
            text=p.text,
            source=PointSource.material,
            weight=p.weight,
        )
        for p in output.points
    ]
