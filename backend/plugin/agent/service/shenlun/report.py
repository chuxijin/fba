from __future__ import annotations

import re

from typing import Any

from backend.plugin.agent.service.shenlun.common import grade_label


def render_grading_report(result: dict[str, Any], rubric: dict[str, Any]) -> str:  # noqa: C901
    """渲染与 YanShen 同契约的申论 Markdown 报告。"""
    score = float(result.get('display_score') if result.get('display_score') is not None else result.get('score') or 0)
    max_score = float(result.get('display_max_score') or rubric.get('max_score') or 100)
    stale = result.get('score_status') == 'stale'
    provisional = result.get('score_status') == 'provisional'
    summary = result.get('summary') if isinstance(result.get('summary'), dict) else {}
    summary_parts = [summary.get('verdict'), *(summary.get('strengths') or []), *(summary.get('weaknesses') or [])]
    overall = '；'.join(str(item).strip('；。 ') for item in summary_parts if str(item or '').strip())
    overall = _safe_overall(overall or result.get('overall_summary'))
    lines = [
        '## 总体评分',
        f'- {"原评分（已过期）" if stale else "总分"}：{_score(score)}/{_score(max_score)}'
        f'{" · 百分制估分" if result.get("score_is_estimated") else ""}',
        f'- 等级：{grade_label(score, max_score)}',
        f'- 综合判断：{overall}',
    ]
    if rubric.get('word_limit'):
        lines.append(f'- 字数要求：{rubric["word_limit"]}')
    if stale:
        lines.append('- 状态：采分点已人工纠正，总分待重新批改；该分数不计入统计。')
    elif provisional:
        lines.append('- 状态：存在尚未解析的关键证据，当前分数待复核且不计入统计。')

    display_scale = max_score / 100
    content_max = (
        next(
            (
                float(item.get('weight') or 0)
                for item in rubric.get('dimensions') or []
                if item.get('dimension') == 'content'
            ),
            0.0,
        )
        * display_scale
    )
    lines.extend([
        '',
        '## 采分点证据与整体校准',
        f'- 加权踩点覆盖参考值：'
        f'{_score(result.get("display_weighted_coverage_score", result.get("weighted_coverage_score")))}'
        f'/{_score(content_max)}',
        f'- 综合内容分：{_score(result.get("display_content_score", result.get("content_score")))}',
    ])
    calibration = result.get('score_calibration') or {}
    if calibration.get('enabled') or calibration.get('adjustment'):
        lines.append(
            f'- 考场锚点校准：{_score(calibration.get("raw_score"))}→{_score(result.get("score"))}'
            f'（{calibration.get("policy_version") or "未标注版本"}）'
        )
    if result.get('holistic_adjustment_reason'):
        lines.append(f'- 整体调整理由：{result["holistic_adjustment_reason"]}')
    reference_count = int(rubric.get('selected_reference_count') or len(rubric.get('selected_references') or []))
    reference_label = '参考答案融合说明' if reference_count > 1 else '参考答案使用说明'
    lines.append(f'- {reference_label}：{result.get("reference_fusion") or "按材料依据核验采分点。"}')

    point_by_key = {point['point_key']: point for point in rubric.get('points') or []}
    status_labels = {'hit': '命中', 'partial': '部分命中', 'miss': '未命中'}
    importance_labels = {'critical': '核心', 'major': '重要', 'supporting': '补充'}
    lines.extend([
        '',
        '## 采分点分析',
        '| 采分点 | 重要性 | 建议权重 | 命中情况 | 用户答案证据 | 判断依据 |',
        '| --- | --- | ---: | --- | --- | --- |',
    ])
    for match in result.get('point_matches') or []:
        point = point_by_key.get(match.get('point_key')) or {}
        status = status_labels.get(match.get('status'), '未命中')
        if match.get('status') == 'partial':
            status += f'（覆盖{round(float(match.get("coverage_ratio") or 0) * 100)}%）'
        if match.get('evidence_status') == 'unresolved' and match.get('status') != 'miss':
            status += ' · 证据待复核'
        lines.append(
            '| {label} | {importance} | {weight} | {status} | {quote} | {reason} |'.format(
                label=_cell(point.get('label') or match.get('point_key')),
                importance=importance_labels.get(point.get('importance'), '补充'),
                weight=_score(float(point.get('weight') or 0) * display_scale),
                status=status,
                quote=_cell(match.get('answer_quote') or '未体现'),
                reason=_cell(match.get('reason') or point.get('weight_reason')),
            )
        )

    lines.extend(['', '## 原文可视化批注'])
    annotation_labels = {
        'good': '亮点',
        'polish': '润色',
        'change': '修改',
        'delete': '删减',
        'add': '补充',
        'critical': '关键',
    }
    for item in result.get('annotations') or []:
        content = item.get('quote') or item.get('replacement') or '建议补充'
        lines.append(
            '- [{kind}|{content}|{reason}|{anchor}|{severity}|{replacement}]'.format(
                kind=annotation_labels.get(item.get('kind'), '修改'),
                content=_annotation(content),
                reason=_annotation(item.get('reason')),
                anchor=_annotation(item.get('anchor')),
                severity=_annotation(item.get('severity')),
                replacement=_annotation(item.get('replacement')),
            )
        )
    if not result.get('annotations'):
        lines.append('- 本次未生成通过原文校验的可视化批注。')

    lines.extend(['', '## 材料领读'])
    lines.extend(f'- {item}' for item in result.get('material_reading') or [])
    if not result.get('material_reading'):
        lines.append('- 请按重要采分点回到对应材料原文定位信息。')

    lines.extend(['', '## 优化建议'])
    suggestions = result.get('optimization_suggestions') or []
    lines.extend(f'{index}. {item}' for index, item in enumerate(suggestions, start=1))
    if not suggestions:
        lines.append('1. 优先修复影响最大的核心问题，再优化结构与表达。')
    for item in result.get('personalized_findings') or []:
        prefix = '重复问题' if item.get('confidence') == 'recurring' else '阶段性观察'
        evidence_ids = '、'.join(item.get('evidence_ids') or [])
        lines.append(f'- {prefix}：{item.get("finding")}（依据：{evidence_ids}）')
        if item.get('root_cause'):
            lines.append(f'  - 深层原因：{item["root_cause"]}')
        if item.get('next_step'):
            lines.append(f'  - 下一步：{item["next_step"]}')
    lines.extend(['', '## 修改版答案', '', result.get('revised_answer') or '（未生成有效修改版答案）'])
    return '\n'.join(lines)


def _score(value: Any) -> str:
    return f'{round(float(value or 0), 2):g}'


def _safe_overall(value: Any) -> str:
    text = str(value or '').strip()
    text = re.sub(r'(?:总评|总分|得分)\s*[：:].*?(?:。|$)', '', text).strip('；。 ')
    return text or '请结合维度得分与采分点分析查看。'


def _cell(value: Any) -> str:
    return str(value or '').replace('|', '／').replace('\n', ' ').strip()


def _annotation(value: Any) -> str:
    return _cell(value).replace(']', '）')
