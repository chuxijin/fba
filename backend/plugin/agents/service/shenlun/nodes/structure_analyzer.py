#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.shenlun.outputs import StructureAnalyzerOutput

# 大作文/应用文需要完整结构分析, 短题(归纳/分析/对策)无议论文结构概念故跳过
_STRUCTURE_REQUIRED_TYPES = {'大作文', '应用文'}


async def analyze_structure(ctx: NodeContext) -> None:
    """段落结构分析"""
    if ctx.state.question_type and ctx.state.question_type not in _STRUCTURE_REQUIRED_TYPES:
        ctx.state.extras['structure'] = {
            'skipped': True,
            'summary': f'{ctx.state.question_type} 题型无需结构分析',
        }
        return

    if not ctx.state.user_answer_text.strip():
        return

    system, user, _ = ctx.prompts.load_and_render(
        'structure_analyzer',
        {
            'user_answer_text': ctx.state.user_answer_text,
        },
    )

    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.mini,
        system_prompt=system,
        user_prompt=user,
        output_type=StructureAnalyzerOutput,
        temperature=0.2,
        max_tokens=8192,
    )
    ctx.last_llm_stats = stats

    ctx.state.extras['structure'] = output.model_dump(mode='json')
