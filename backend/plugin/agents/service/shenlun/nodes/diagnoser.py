#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.agents.schema import (
    IssueItem,
    IssuesSection,
    SectionName,
    Severity,
)
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext, NodeContractError
from backend.plugin.agents.service.shenlun.outputs import DiagnoserOutput


async def diagnose(ctx: NodeContext) -> None:
    """问题诊断"""
    if ctx.state.score_card is None:
        raise NodeContractError('diagnoser 要求 score_card 已就绪, 上游 scorer 可能失败')

    sc = ctx.state.score_card
    key_points = ctx.state.key_points
    missing_count = 0
    missing_summary = ''
    if key_points:
        missing_pts = [rp for rp in key_points.reference_points if not rp.matched_user_text]
        missing_count = len(missing_pts)
        missing_summary = '; '.join(rp.text for rp in missing_pts)[:500]

    structure_summary = (ctx.state.extras.get('structure') or {}).get('summary', '未分析')

    system, user, _ = ctx.prompts.load_and_render(
        'diagnoser',
        {
            'score_total': sc.score,
            'score_max': sc.score_total,
            'level': sc.level,
            'level_label': sc.level_label,
            'rubric_scores': sc.rubric_scores,
            'missing_count': missing_count,
            'missing_summary': missing_summary,
            'structure_summary': structure_summary,
            'user_answer_text': ctx.state.user_answer_text,
        },
    )

    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=DiagnoserOutput,
        temperature=0.3,
        max_tokens=8192,
    )
    ctx.last_llm_stats = stats

    items = [
        IssueItem(
            category=raw.category,
            severity=Severity(raw.severity),
            description=raw.description,
            location=raw.location,
            related_section=SectionName(raw.related_section) if raw.related_section else None,
        )
        for raw in output.issues
    ]
    ctx.state.issues = IssuesSection(items=items)
