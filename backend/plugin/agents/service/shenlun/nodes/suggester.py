#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.agents.schema import Priority, SuggestionItem, SuggestionsSection
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext, NodeContractError
from backend.plugin.agents.service.shenlun.outputs import SuggesterOutput


async def suggest(ctx: NodeContext) -> None:
    """提升建议"""
    if ctx.state.issues is None:
        raise NodeContractError('suggester 要求 issues 已就绪, 上游 diagnoser 可能失败')

    key_points = ctx.state.key_points
    missing_summary = ''
    if key_points:
        missing_pts = [rp for rp in key_points.reference_points if not rp.matched_user_text]
        missing_summary = '; '.join(rp.text for rp in missing_pts)[:500]

    system, user, _ = ctx.prompts.load_and_render(
        'suggester',
        {
            'issues': ctx.state.issues.items,
            'user_answer_text': ctx.state.user_answer_text,
            'missing_summary': missing_summary,
        },
    )

    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=SuggesterOutput,
        temperature=0.4,
        max_tokens=2000,
    )
    ctx.last_llm_stats = stats

    items = [
        SuggestionItem(
            target_issue=raw.target_issue,
            action=raw.action,
            priority=Priority(raw.priority),
        )
        for raw in output.suggestions
    ]
    ctx.state.suggestions = SuggestionsSection(items=items)
