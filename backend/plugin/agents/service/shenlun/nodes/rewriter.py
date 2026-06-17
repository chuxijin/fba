#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re

from backend.plugin.agents.schema import ChangeItem, RewrittenTextSection
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext, NodeContractError
from backend.plugin.agents.service.shenlun.outputs import RewriterOutput


async def rewrite(ctx: NodeContext) -> None:
    """改写示范"""
    original = ctx.state.user_answer_text
    if not original.strip():
        raise NodeContractError('rewriter 要求 user_answer_text 非空')

    issues = ctx.state.issues.items if ctx.state.issues else []
    suggestions = ctx.state.suggestions.items if ctx.state.suggestions else []

    key_points = ctx.state.key_points
    missing_summary = ''
    if key_points:
        missing_pts = [rp for rp in key_points.reference_points if not rp.matched_user_text]
        missing_summary = '; '.join(rp.text for rp in missing_pts)[:500]

    word_limit_hint = _extract_word_limit(ctx.state.question, len(original))

    system, user, _ = ctx.prompts.load_and_render(
        'rewriter',
        {
            'user_answer_text': original,
            'question': ctx.state.question,
            'word_limit_hint': word_limit_hint,
            'original_length': len(original),
            'issues': issues,
            'suggestions': suggestions,
            'missing_summary': missing_summary,
        },
    )

    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=RewriterOutput,
        temperature=0.6,
        max_tokens=8192,
    )
    ctx.last_llm_stats = stats

    revised_text = output.revised

    # 超字数二次压缩
    upper_limit = _extract_upper_limit(ctx.state.question)
    if upper_limit and len(revised_text) > upper_limit:
        revised_text = await _compress_to_limit(ctx, revised_text, upper_limit, original)

    # 构建 changes 列表
    changes = [
        ChangeItem(
            original=c.original,
            revised=c.revised,
            reason=c.reason,
        )
        for c in output.changes
    ]

    # 生成行内对比格式
    inline_diff = _build_inline_diff(original, revised_text, changes)

    ctx.state.rewritten_text = RewrittenTextSection(
        original=original,
        revised=revised_text,
        diff_summary=output.diff_summary,
        changes=changes,
        inline_diff=inline_diff,
    )


def _build_inline_diff(
    original: str,
    revised: str,
    changes: list,
) -> str:
    """
    根据 changes 生成行内对比格式

    :param original: 用户原文
    :param revised: 改写文本
    :param changes: ChangeItem 列表
    :return: 带删除线和加粗的行内对比文本
    """
    if not changes:
        return revised

    result = original
    for change in changes:
        orig_text = change.original
        new_text = change.revised
        if orig_text and orig_text in result:
            result = result.replace(
                orig_text,
                f'~~{orig_text}~~**{new_text}**',
                1,
            )
    return result


def _extract_word_limit(question: str, original_length: int) -> str:
    """从题目要求中提取字数限制提示"""
    upper = re.search(r'不超过\s*(\d+)\s*字', question)
    lower = re.search(r'不少于\s*(\d+)\s*字', question)
    range_match = re.search(r'(\d+)\s*[-—至]\s*(\d+)\s*字', question)

    if range_match:
        return f'改写后字数必须在 {range_match.group(1)}-{range_match.group(2)} 字之间, 不得超过'
    if upper and lower:
        return f'改写后字数必须在 {lower.group(1)}-{upper.group(1)} 字之间'
    if upper:
        return f'改写后字数严格不超过 {upper.group(1)} 字, 不允许超出'
    if lower:
        return f'改写后字数不少于 {lower.group(1)} 字'

    lower_bound = max(int(original_length * 0.8), 100)
    upper_bound = int(original_length * 1.2)
    return f'题目未指定字数, 按原文 ±20% 改写, 建议 {lower_bound}-{upper_bound} 字'


def _extract_upper_limit(question: str) -> int | None:
    """提取字数上限"""
    upper = re.search(r'不超过\s*(\d+)\s*字', question)
    if upper:
        return int(upper.group(1))
    range_match = re.search(r'(\d+)\s*[-—至]\s*(\d+)\s*字', question)
    if range_match:
        return int(range_match.group(2))
    return None


async def _compress_to_limit(
    ctx: NodeContext,
    text: str,
    limit: int,
    original: str,
) -> str:
    """
    超字数时调 LLM 二次压缩

    :param ctx: 节点上下文
    :param text: 超字数的改写文本
    :param limit: 字数上限
    :param original: 原始考生答案
    :return: 压缩后的文本
    """
    system_prompt = (
        f'你是申论改写压缩专家。请将以下改写文本压缩到 {limit} 字以内，'
        f'保持核心观点和论证逻辑不变，删除冗余表述和重复论据。'
        f'只返回压缩后的文本，不要其他内容。'
    )
    user_prompt = (
        f'## 原始考生答案 ({len(original)} 字)\n{original}\n\n'
        f'## 需要压缩的改写文本 ({len(text)} 字，要求压缩到 {limit} 字以内)\n{text}'
    )

    compressed, stats = await ctx.llm.invoke_text(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.3,
        max_tokens=8192,
    )
    ctx.last_llm_stats = stats

    # 如果压缩后仍然超限, 截断到上限
    if len(compressed) > limit:
        compressed = compressed[:limit]

    return compressed
