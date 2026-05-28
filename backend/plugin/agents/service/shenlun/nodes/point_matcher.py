#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.shenlun.outputs import PointMatcherOutput


async def match_points(ctx: NodeContext) -> None:
    """要点匹配, 回填参考要点的命中信息并产出 missing_points"""
    section = ctx.state.key_points
    if section is None or not section.reference_points:
        return

    system, user, _ = ctx.prompts.load_and_render(
        'point_matcher',
        {
            'reference_points': section.reference_points,
            'answer_points': section.answer_points,
        },
    )

    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=PointMatcherOutput,
        temperature=0.1,
        max_tokens=2000,
    )
    ctx.last_llm_stats = stats

    matched_dict: dict[str, str] = {
        item.reference_point_text: item.matched_user_text for item in output.matched
    }

    section.reference_points = [
        rp.model_copy(update={'matched_user_text': matched_dict.get(rp.text)})
        for rp in section.reference_points
    ]

    missing_keys = {item.reference_point_text for item in output.missing}
    section.missing_points = [
        rp for rp in section.reference_points if rp.text in missing_keys
    ]

    if not section.missing_points:
        section.missing_points = [
            rp for rp in section.reference_points if rp.matched_user_text is None
        ]
