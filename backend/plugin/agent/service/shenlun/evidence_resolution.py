from __future__ import annotations

import re
import unicodedata

from typing import Any

_ELLIPSIS_RE = re.compile(r'(?:…{1,}|\.{3,})')


def _search_form(value: str) -> tuple[str, list[int]]:
    normalized: list[str] = []
    positions: list[int] = []
    for index, char in enumerate(str(value or '')):
        for candidate in unicodedata.normalize('NFKC', char):
            if candidate.isspace() or unicodedata.category(candidate).startswith('P'):
                continue
            normalized.append(candidate.casefold())
            positions.append(index)
    return ''.join(normalized), positions


def _span(answer_text: str, start: int, end: int, mode: str) -> dict[str, Any]:
    return {'start': start, 'end': end, 'text': answer_text[start:end], 'mode': mode}


def resolve_answer_evidence(quote: str, answer_text: str) -> dict[str, Any]:
    """定位模型引用，避免标点和格式差异造成误判。

    Adapted from Nullapse/YanShen under the MIT License.
    """
    quote = str(quote or '').strip()
    answer_text = str(answer_text or '')
    if not quote or not answer_text:
        return {'status': 'unresolved', 'quote': quote, 'spans': []}
    exact_start = answer_text.find(quote)
    if exact_start >= 0:
        span = _span(answer_text, exact_start, exact_start + len(quote), 'exact')
        return {'status': 'resolved', 'quote': span['text'], 'spans': [span]}
    fragments = [value.strip() for value in _ELLIPSIS_RE.split(quote) if value.strip()]
    if len(fragments) > 1:
        spans: list[dict[str, Any]] = []
        cursor = 0
        for fragment in fragments:
            resolved = resolve_answer_evidence(fragment, answer_text[cursor:])
            if resolved['status'] != 'resolved' or not resolved['spans']:
                spans = []
                break
            for item in resolved['spans']:
                shifted = dict(item)
                shifted['start'] += cursor
                shifted['end'] += cursor
                shifted['mode'] = 'ordered_fragments'
                spans.append(shifted)
            cursor = spans[-1]['end']
        if spans:
            return {'status': 'resolved', 'quote': '……'.join(item['text'] for item in spans), 'spans': spans}
    answer_search, answer_positions = _search_form(answer_text)
    quote_search, _ = _search_form(quote)
    normalized_start = answer_search.find(quote_search) if quote_search else -1
    if normalized_start >= 0:
        source_start = answer_positions[normalized_start]
        source_end = answer_positions[normalized_start + len(quote_search) - 1] + 1
        span = _span(answer_text, source_start, source_end, 'normalized')
        return {'status': 'resolved', 'quote': span['text'], 'spans': [span]}
    return {'status': 'unresolved', 'quote': quote, 'spans': []}
