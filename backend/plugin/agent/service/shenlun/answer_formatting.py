from __future__ import annotations

import re

from typing import Any

ANSWER_GRID_COLUMNS = 25


def answer_grid_metrics(text: str, columns: int = ANSWER_GRID_COLUMNS) -> dict[str, int]:
    """按申论答题纸占格规则计算正文占格数。"""
    columns = max(1, int(columns or ANSWER_GRID_COLUMNS))
    logical_lines = str(text or '').replace('\r\n', '\n').replace('\r', '\n').split('\n')
    occupied_cells = 0
    occupied_lines = 0
    current_line_cells = 0
    last_index = len(logical_lines) - 1
    for index, line in enumerate(logical_lines):
        if index < last_index and not line:
            continue
        content_cells = _grid_cells_for_line(line)
        current_line_cells = ((content_cells - 1) % columns) + 1 if content_cells else 0
        if index < last_index:
            line_count = (content_cells + columns - 1) // columns
            occupied_cells += line_count * columns
            occupied_lines += line_count
        else:
            occupied_cells += content_cells
            occupied_lines += (content_cells + columns - 1) // columns
    return {
        'occupied_cells': occupied_cells,
        'lines': occupied_lines,
        'columns': columns,
        'current_line_cells': current_line_cells,
    }


def compact_revised_answer_linebreaks(text: str, word_limit: str = '') -> str:
    """在不改变正文措辞的前提下，合并低价值换行以适配答题纸。"""
    original = str(text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    hard_max = word_limit_budget(word_limit)['hard_max_exclusive']
    if not original or not hard_max or answer_grid_metrics(original)['occupied_cells'] < hard_max:
        return original
    lines = [line.strip() for line in original.split('\n') if line.strip()]
    if len(lines) < 4 or answer_grid_metrics(''.join(lines))['occupied_cells'] >= hard_max:
        return original
    while answer_grid_metrics('\n'.join(lines))['occupied_cells'] >= hard_max:
        candidates: list[tuple[int, int, list[str]]] = []
        for index in range(1, len(lines) - 3):
            left, right = lines[index], lines[index + 1]
            separator = ' ' if left[-1:].isalnum() and right[:1].isalnum() and left[-1:].isascii() else ''
            merged = [*lines[:index], left + separator + right, *lines[index + 2 :]]
            reduction = (
                answer_grid_metrics('\n'.join(lines))['occupied_cells']
                - answer_grid_metrics('\n'.join(merged))['occupied_cells']
            )
            if reduction > 0:
                candidates.append((reduction, index, merged))
        if not candidates:
            return original
        _, _, lines = max(candidates, key=lambda item: (item[0], -item[1]))
    return '\n'.join(lines)


def word_limit_budget(value: str) -> dict[str, Any]:
    raw = str(value or '').strip()
    compact = re.sub(r'\s+', '', raw)
    numbers = [int(number) for number in re.findall(r'\d+', compact)]
    budget: dict[str, Any] = {
        'raw': raw,
        'mode': 'none',
        'minimum': 0,
        'suggested_min': 0,
        'suggested_max': 0,
        'hard_max_exclusive': 0,
    }
    if not numbers:
        return budget
    if '左右' in compact:
        target = numbers[-1]
        if target <= 500:
            _set_hard_max_budget(budget, target)
        else:
            budget.update(
                mode='approximate',
                suggested_min=max(1, round(target * 0.95)),
                suggested_max=max(1, round(target * 1.05)),
            )
        return budget
    if re.search(r'(?:不少于|不低于|至少|以上)', compact):
        minimum = numbers[-1]
        budget.update(
            mode='minimum',
            minimum=minimum,
            suggested_min=minimum,
            suggested_max=max(minimum, round(minimum * 1.1)),
        )
        return budget
    if len(numbers) >= 2 and re.search(r'[-—–~～至到]', compact):
        lower, upper = sorted(numbers[-2:])
        target_min = min(upper - 1, max(lower, int(upper * 0.9 + 0.999999)))
        target_max = min(upper - 1, max(target_min, int(upper * 0.96)))
        budget.update(
            mode='range',
            minimum=lower,
            suggested_min=max(0, target_min),
            suggested_max=max(0, target_max),
            hard_max_exclusive=upper,
        )
        return budget
    _set_hard_max_budget(budget, numbers[-1])
    return budget


def normalize_revised_answer_word_count(report_text: str, word_limit: str = '') -> str:
    section = split_revised_answer_section(report_text)
    if not section:
        return report_text
    section_start, body_start, body_end = section
    heading = report_text[section_start:body_start]
    answer_body = revised_answer_body(report_text[body_start:body_end])
    if not answer_body:
        return report_text
    actual_chars = answer_grid_metrics(answer_body)['occupied_cells']
    budget = word_limit_budget(word_limit)
    hard_max = budget['hard_max_exclusive']
    over_limit = bool(hard_max and actual_chars >= hard_max)
    status_line = _word_count_line(actual_chars, budget)
    warning = '> 系统提示：修改版答案未满足严格硬限制，不能直接作为最终答案使用；请继续压缩。\n\n'
    normalized = heading + '\n' + status_line + '\n\n' + (warning if over_limit else '') + answer_body
    suffix = report_text[body_end:]
    if suffix:
        normalized += '\n\n'
    return report_text[:section_start] + normalized + suffix


def revised_answer_word_count_status(report_text: str, word_limit: str = '') -> dict[str, Any]:
    section = split_revised_answer_section(report_text)
    budget = word_limit_budget(word_limit)
    hard_max = budget['hard_max_exclusive']
    if not section:
        return {
            'has_revised_answer': False,
            'actual_chars': 0,
            'max_chars': hard_max,
            'budget': budget,
            'budget_status': 'missing',
            'over_limit': False,
            'over_by': 0,
        }
    _, body_start, body_end = section
    answer_body = revised_answer_body(report_text[body_start:body_end])
    actual_chars = answer_grid_metrics(answer_body)['occupied_cells']
    over_by = actual_chars - hard_max + 1 if hard_max and actual_chars >= hard_max else 0
    return {
        'has_revised_answer': bool(answer_body),
        'actual_chars': actual_chars,
        'max_chars': hard_max,
        'budget': budget,
        'budget_status': _budget_status_label(actual_chars, budget),
        'over_limit': over_by > 0,
        'over_by': over_by,
    }


def split_revised_answer_section(report_text: str) -> tuple[int, int, int] | None:
    match = re.search(r'(?m)^##\s*修改版答案\s*$', report_text or '')
    if not match:
        return None
    body_start = match.end()
    next_match = re.search(r'(?m)^##\s+', report_text[body_start:])
    body_end = body_start + next_match.start() if next_match else len(report_text)
    return match.start(), body_start, body_end


def revised_answer_body(section_text: str) -> str:
    lines = section_text.strip('\n').splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and re.match(r'^\s*(?:[-*]\s*)?(?:估算|实际)?字数\s*[:：]', lines[0]):
        lines.pop(0)
    while lines and (not lines[0].strip() or lines[0].strip().startswith('> 系统提示：')):
        lines.pop(0)
    return '\n'.join(lines).strip()


def build_revised_answer_retry_prompt(original_prompt: str, report_text: str, word_limit: str) -> str:
    status = revised_answer_word_count_status(report_text, word_limit)
    budget = status['budget']
    return '\n'.join([
        '你刚才生成的批改报告中，修改版答案未满足严格字数限制。',
        f'系统按25格答题纸规则复核：实际占格 {status["actual_chars"]} 字；硬限制为低于 {status["max_chars"]} 字。',
        f'本次返修目标：{budget["suggested_min"]}—{budget["suggested_max"]} 字。',
        '请只返回 JSON：{"revised_answer": "压缩后的答案正文"}。',
        '压缩时保留核心采分点、题目要求的文种和必要结构，不得增加无材料依据的内容。',
        f'原批改任务：{original_prompt}',
        f'上一版报告：{report_text}',
    ])


def _grid_cells_for_line(text: str) -> int:
    characters = list(text or '')
    cells = 0
    index = 0
    while index < len(characters):
        character = characters[index]
        if character in {'—', '…'}:
            cells += 2
            index += 2 if index + 1 < len(characters) and characters[index + 1] == character else 1
            continue
        if character.isascii() and character.isalnum():
            end = index + 1
            while end < len(characters) and characters[end].isascii() and characters[end].isalnum():
                end += 1
            cells += (end - index + 1) // 2
            index = end
            continue
        cells += 1
        index += 1
    return cells


def _set_hard_max_budget(budget: dict[str, Any], hard_max: int) -> None:
    target_min = min(hard_max - 1, int(hard_max * 0.9 + 0.999999))
    target_max = min(hard_max - 1, max(target_min, int(hard_max * 0.96)))
    budget.update(
        mode='hard_max',
        suggested_min=max(0, target_min),
        suggested_max=max(0, target_max),
        hard_max_exclusive=hard_max,
    )


def _budget_status_label(actual_chars: int, budget: dict[str, Any]) -> str:
    hard_max = budget['hard_max_exclusive']
    if hard_max and actual_chars >= hard_max:
        return '超出硬限制'
    if budget['mode'] == 'minimum':
        return '符合最低要求' if actual_chars >= budget['minimum'] else '低于最低要求'
    if budget['mode'] == 'range' and actual_chars < budget['minimum']:
        return '符合硬限制，低于最低要求'
    if not budget['suggested_min']:
        return '未标注字数要求'
    if actual_chars < budget['suggested_min']:
        return '符合字数要求，篇幅偏短' if hard_max else '低于建议区间'
    if actual_chars <= budget['suggested_max']:
        return '符合字数要求，处于建议区间' if hard_max else '处于建议区间'
    return '符合字数要求，接近上限' if hard_max else '高于建议区间'


def _word_count_line(actual_chars: int, budget: dict[str, Any]) -> str:
    parts = [f'实际字数：{actual_chars}字']
    if budget['suggested_min']:
        parts.append(f'建议区间：{budget["suggested_min"]}—{budget["suggested_max"]}字')
    if budget['hard_max_exclusive']:
        parts.append(f'硬限制：低于{budget["hard_max_exclusive"]}字')
    elif budget['minimum']:
        parts.append(f'最低要求：不少于{budget["minimum"]}字')
    else:
        parts.append('硬限制：未标注')
    parts.append(f'状态：{_budget_status_label(actual_chars, budget)}')
    return '；'.join(parts)
