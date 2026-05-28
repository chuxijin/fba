#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re

from backend.plugin.agents.schema import (
    ConsensusLevel,
    GradeLevel,
    RubricScoreItem,
    ScoreCardSection,
)
from backend.plugin.agents.service.common.llm import NodeRole
from backend.plugin.agents.service.common.orchestrator import NodeContext, NodeContractError
from backend.plugin.agents.service.shenlun.outputs import ScorerOutput


async def score(ctx: NodeContext) -> None:
    """分维度评分与总评"""
    if ctx.state.rubric is None or not ctx.state.rubric.get('dimensions'):
        raise NodeContractError('scorer 要求 rubric.dimensions 非空, 上游 rubric_loader 可能失败')
    if ctx.state.key_points is None:
        raise NodeContractError('scorer 要求 key_points 已初始化, 上游 rubric_loader 可能失败')
    if not ctx.state.user_answer_text.strip():
        raise NodeContractError('scorer 要求 user_answer_text 非空')

    rubric = ctx.state.rubric

    key_points = ctx.state.key_points
    covered_count = 0
    covered_high_count = 0
    missing_count = 0
    missing_high_count = 0
    missing_summary = ''
    if key_points:
        ref_points = key_points.reference_points
        covered = [rp for rp in ref_points if rp.matched_user_text]
        missing = [rp for rp in ref_points if not rp.matched_user_text]
        covered_count = len(covered)
        missing_count = len(missing)
        covered_high_count = sum(1 for rp in covered if rp.consensus_level == ConsensusLevel.high)
        missing_high_count = sum(1 for rp in missing if rp.consensus_level == ConsensusLevel.high)
        missing_summary = '; '.join(rp.text for rp in missing)[:500]

    structure_summary = (ctx.state.extras.get('structure') or {}).get('summary', '未分析')

    system, user, _ = ctx.prompts.load_and_render(
        'scorer',
        {
            'rubric': rubric,
            'question': ctx.state.question,
            'user_answer_text': ctx.state.user_answer_text,
            'covered_count': covered_count,
            'covered_high_count': covered_high_count,
            'missing_count': missing_count,
            'missing_high_count': missing_high_count,
            'missing_summary': missing_summary,
            'structure_summary': structure_summary,
        },
    )

    output, stats = await ctx.llm.invoke_structured(
        ctx.db,
        role=NodeRole.primary,
        system_prompt=system,
        user_prompt=user,
        output_type=ScorerOutput,
        temperature=0.1,
        max_tokens=2500,
    )
    ctx.last_llm_stats = stats

    rubric_scores = [
        RubricScoreItem(
            name=item.name,
            score=item.score,
            max_score=item.max_score,
            level=GradeLevel(item.level) if item.level else None,
            level_label=item.level_label,
            comment=item.comment,
        )
        for item in output.rubric_scores
    ]

    rubric_total_max = float(rubric.get('total', ctx.state.score_total))
    llm_total = round(sum(item.score for item in rubric_scores), 1)

    cap_factor, cap_reason = _compute_cap_factor(
        user_text=ctx.state.user_answer_text,
        materials=ctx.state.materials,
        question=ctx.state.question,
        missing_high_count=missing_high_count,
        question_type=ctx.state.question_type,
    )

    if cap_factor < 1.0:
        rubric_scores = _apply_score_cap(rubric_scores, llm_total, rubric_total_max, cap_factor)

    calculated_total = round(sum(item.score for item in rubric_scores), 1)

    # 兜底: 硬性上限, LLM 可能给出超过满分的分项
    if calculated_total > rubric_total_max:
        scale = rubric_total_max / calculated_total
        rubric_scores = [
            item.model_copy(update={'score': round(item.score * scale, 1)})
            for item in rubric_scores
        ]
        calculated_total = rubric_total_max

    calculated_level = _level_from_ratio(calculated_total, rubric_total_max)
    grade_labels = rubric.get('grade_labels') or {}
    calculated_label = grade_labels.get(calculated_level.value) or output.level_label

    system_notes: list[str] = []
    if cap_factor < 1.0 and cap_reason:
        system_notes.append(f'代码层强制扣分: {cap_reason}')

    ctx.state.score_card = ScoreCardSection(
        score=calculated_total,
        score_total=rubric_total_max,
        level=calculated_level,
        level_label=calculated_label,
        summary=output.summary,
        rubric_scores=rubric_scores,
        system_notes=system_notes,
    )


def _level_from_ratio(score: float, max_score: float) -> GradeLevel:
    """根据分数比例换算档位 (友好版阈值, C 端考生体验导向)"""
    if max_score <= 0:
        return GradeLevel.c
    ratio = score / max_score
    if ratio >= 0.85:
        return GradeLevel.a
    if ratio >= 0.65:
        return GradeLevel.b
    if ratio >= 0.40:
        return GradeLevel.c
    return GradeLevel.d


def _extract_word_limits(question: str) -> tuple[int | None, int | None]:
    """从题目要求中提取字数下限/上限"""
    lower: int | None = None
    upper: int | None = None

    if m := re.search(r'(\d+)\s*[-—至]\s*(\d+)\s*字', question):
        lower = int(m.group(1))
        upper = int(m.group(2))
    else:
        if m := re.search(r'不少于\s*(\d+)\s*字', question):
            lower = int(m.group(1))
        if m := re.search(r'不超过\s*(\d+)\s*字', question):
            upper = int(m.group(1))

    return lower, upper


def _count_material_citations(text: str, materials: str) -> int:
    """粗略统计材料引用次数 (数据/案例/人物名)"""
    count = 0
    count += len(re.findall(r'\d+(?:\.\d+)?\s*[万亿千百十%]', text))
    count += len(re.findall(r'材料\s*[一二三四五六七八九十\d]+', text))
    count += len(re.findall(r'"[^"]{6,40}"', text))

    if materials:
        name_pattern = re.findall(r'[A-Z]?[一-龥]{2,4}(?:主任|教授|经理|大爷|女士|总|先生|博士)', materials)
        for name in set(name_pattern):
            if name in text:
                count += 1

    return count


def _compute_cap_factor(
    user_text: str,
    materials: str,
    question: str,
    missing_high_count: int,
    question_type: str | None = None,
) -> tuple[float, str]:
    """
    计算总分硬上限因子 (越小越严), 同时返回触发原因

    :param user_text: 考生答案
    :param materials: 给定材料
    :param question: 题目要求
    :param missing_high_count: 缺失的 high consensus 要点数
    :param question_type: 题型 (如 "应用文")
    :return:
    """
    factors: list[tuple[float, str]] = []
    text_length = len(user_text)

    lower_limit, _ = _extract_word_limits(question)
    if lower_limit:
        if text_length < lower_limit * 0.5:
            factors.append((0.35, f'字数 {text_length} 严重不足 (要求下限 {lower_limit})'))
        elif text_length < lower_limit * 0.8:
            factors.append((0.6, f'字数 {text_length} 中度不足 (要求下限 {lower_limit})'))

    citations = _count_material_citations(user_text, materials)
    if materials.strip():
        if citations == 0:
            factors.append((0.5, '全文无具体材料引用 (数据/案例/人物)'))
        elif citations == 1:
            factors.append((0.7, '材料引用仅 1 处, 论证薄弱'))

    if missing_high_count >= 3:
        factors.append((0.6, f'缺失 {missing_high_count} 条高共识要点'))
    elif missing_high_count >= 2:
        factors.append((0.85, f'缺失 {missing_high_count} 条高共识要点'))

    # 应用文格式检测
    if question_type == '应用文':
        format_factor, format_reason = _check_application_format(user_text)
        if format_factor < 1.0:
            factors.append((format_factor, format_reason))

    # 综合分析/提出对策题型额外扣分 (10 分制题型, 防止评分偏高)
    if question_type in ('综合分析', '提出对策'):
        # 如果字数不足且材料引用少, 说明分析/论证不充分
        if lower_limit and text_length < lower_limit * 0.85 and citations <= 1:
            factors.append((0.75, f'10 分制题型: 字数不足 ({text_length}/{lower_limit}) 且论证薄弱'))

    if not factors:
        return 1.0, ''

    min_factor, reason = min(factors, key=lambda x: x[0])
    return min_factor, reason


def _check_application_format(text: str) -> tuple[float, str]:
    """
    检查应用文格式要素 (标题/称呼/落款/日期)

    :param text: 考生答案
    :return: (cap_factor, reason)
    """
    missing_elements: list[str] = []

    # 检查标题 (如 "关于...的通知/方案/倡议书/讲话稿")
    if not re.search(r'关于.{2,20}(?:通知|方案|倡议书|讲话稿|意见|报告|请示|函)', text):
        missing_elements.append('标题')

    # 检查称呼 (如 "尊敬的/各位/同志们/朋友们")
    if not re.search(r'(?:尊敬的|各位|同志们|朋友们|各位领导|各位同事|各位委员)', text):
        missing_elements.append('称呼')

    # 检查落款 (如 "此致敬礼/特此通知/特此报告")
    if not re.search(r'(?:此致\s*敬礼|特此通知|特此报告|特此请示|以上建议|以上报告)', text):
        missing_elements.append('落款')

    # 检查署名/日期 (如 "XX局/2026年")
    has_signer = bool(re.search(r'(?:[一-龥]{2,6}(?:局|委|办|处|室|所|院)|市民政局|市政府)', text))
    has_date = bool(re.search(r'(?:20\d{2}\s*年|\d{1,2}\s*月)', text))

    if not has_signer and not has_date:
        missing_elements.append('署名/日期')

    if not missing_elements:
        return 1.0, ''

    # 根据缺失要素数量决定扣分力度
    if len(missing_elements) >= 3:
        return 0.7, f'应用文格式严重缺失: {", ".join(missing_elements)}'
    return 0.85, f'应用文格式要素缺失: {", ".join(missing_elements)}'


def _apply_score_cap(
    rubric_scores: list[RubricScoreItem],
    current_total: float,
    max_total: float,
    cap_factor: float,
) -> list[RubricScoreItem]:
    """
    按比例缩放各维度分数, 使总分不超过 max_total * cap_factor

    :param rubric_scores: 原始评分
    :param current_total: 当前总分
    :param max_total: 满分
    :param cap_factor: 上限因子
    :return:
    """
    max_allowed = max_total * cap_factor
    if current_total <= max_allowed or current_total <= 0:
        return rubric_scores

    scale = max_allowed / current_total
    capped: list[RubricScoreItem] = []
    for item in rubric_scores:
        new_score = round(item.score * scale, 1)
        new_level = _dim_level_from_ratio(new_score, item.max_score)
        capped.append(
            item.model_copy(
                update={
                    'score': new_score,
                    'level': new_level,
                }
            )
        )
    return capped


def _dim_level_from_ratio(score: float, max_score: float) -> GradeLevel | None:
    """根据维度分数比例换算档位"""
    if max_score <= 0:
        return None
    ratio = score / max_score
    if ratio >= 0.85:
        return GradeLevel.a
    if ratio >= 0.65:
        return GradeLevel.b
    if ratio >= 0.40:
        return GradeLevel.c
    return GradeLevel.d
