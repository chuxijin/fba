#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.question_generation.outputs import ArticleAnalysisOutput


async def analyze_article(ctx: NodeContext) -> None:
    """分析文章结构"""
    state = ctx.state
    if state.article_analysis:
        return

    system, user, _ = ctx.prompts.load_and_render(
        'article_analyzer',
        {
            'profile': state.profile,
            'material_title': state.material_title,
            'material_content': state.material_content,
        },
    )
    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.mini,
        system_prompt=system,
        user_prompt=user,
        output_type=ArticleAnalysisOutput,
        temperature=0.1,
        max_tokens=8192,
    )
    ctx.last_llm_stats = stats
    state.article_analysis = output.model_dump(mode='json')
