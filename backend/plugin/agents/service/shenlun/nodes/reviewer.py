#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.agents.schema import ConsensusLevel, QCSection
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.shenlun.outputs import ReviewerOutput


async def review(ctx: NodeContext) -> None:
    """质检"""
    sc = ctx.state.score_card
    if sc is None:
        ctx.state.qc = QCSection(
            passed=False,
            confidence=0.0,
            notes=['评分卡缺失, 无法质检'],
            retry_count=0,
        )
        return

    issues = ctx.state.issues.items if ctx.state.issues else []
    suggestions = ctx.state.suggestions.items if ctx.state.suggestions else []

    key_points = ctx.state.key_points
    missing_count = 0
    missing_high_count = 0
    missing_summary = ''
    if key_points:
        missing_pts = [rp for rp in key_points.reference_points if not rp.matched_user_text]
        missing_count = len(missing_pts)
        missing_high_count = sum(
            1 for rp in missing_pts if rp.consensus_level == ConsensusLevel.high
        )
        missing_summary = '; '.join(rp.text for rp in missing_pts)[:500]

    rewritten = ctx.state.rewritten_text
    original_length = len(ctx.state.user_answer_text)
    revised_length = len(rewritten.revised) if rewritten else 0
    revised_diff_summary = rewritten.diff_summary if rewritten else ''

    system, user, _ = ctx.prompts.load_and_render(
        'reviewer',
        {
            'score_total': sc.score,
            'score_max': sc.score_total,
            'level': sc.level,
            'level_label': sc.level_label,
            'score_summary': sc.summary,
            'rubric_scores': sc.rubric_scores,
            'missing_count': missing_count,
            'missing_high_count': missing_high_count,
            'missing_summary': missing_summary,
            'issues': issues,
            'suggestions': suggestions,
            'original_length': original_length,
            'revised_length': revised_length,
            'revised_diff_summary': revised_diff_summary,
        },
    )

    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=ReviewerOutput,
        temperature=0.3,
        max_tokens=8192,
    )
    ctx.last_llm_stats = stats

    ctx.state.qc = QCSection(
        passed=output.passed,
        confidence=output.confidence,
        notes=list(output.notes),
        retry_count=0,
    )
