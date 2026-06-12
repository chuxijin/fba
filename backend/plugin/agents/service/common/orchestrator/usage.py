#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from backend.plugin.agents.schema import AgentTraceItem


def build_usage_summary(traces: list[AgentTraceItem] | list[dict[str, Any]]) -> dict[str, Any]:
    """
    汇总 Agent 执行耗时与 token 用量

    :param traces: 执行轨迹
    :return:
    """
    normalized_traces = [_normalize_trace(trace) for trace in traces]
    if not normalized_traces:
        return {
            'node_count': 0,
            'duration_ms': 0,
            'wall_duration_ms': 0,
            'llm_duration_ms': 0,
            'tokens_in': 0,
            'tokens_out': 0,
            'tokens_total': 0,
            'model_usage': [],
        }

    duration_ms = sum(int(trace.get('duration_ms') or 0) for trace in normalized_traces)
    llm_duration_ms = sum(
        int(trace.get('duration_ms') or 0)
        for trace in normalized_traces
        if trace.get('model')
    )
    tokens_in = sum(int(trace.get('tokens_in') or 0) for trace in normalized_traces)
    tokens_out = sum(int(trace.get('tokens_out') or 0) for trace in normalized_traces)
    started_times = [
        started_at
        for started_at in (_parse_datetime(trace.get('started_at')) for trace in normalized_traces)
        if started_at is not None
    ]
    finished_times = [
        finished_at
        for finished_at in (_parse_datetime(trace.get('finished_at')) for trace in normalized_traces)
        if finished_at is not None
    ]

    wall_duration_ms = 0
    if started_times and finished_times:
        wall_duration_ms = int((max(finished_times) - min(started_times)).total_seconds() * 1000)

    return {
        'node_count': len(normalized_traces),
        'duration_ms': duration_ms,
        'wall_duration_ms': wall_duration_ms,
        'llm_duration_ms': llm_duration_ms,
        'tokens_in': tokens_in,
        'tokens_out': tokens_out,
        'tokens_total': tokens_in + tokens_out,
        'model_usage': _build_model_usage(normalized_traces),
    }


def _normalize_trace(trace: AgentTraceItem | dict[str, Any]) -> dict[str, Any]:
    """
    规范执行轨迹

    :param trace: 执行轨迹
    :return:
    """
    if isinstance(trace, AgentTraceItem):
        return trace.model_dump(mode='json')
    return dict(trace)


def _parse_datetime(value: Any) -> datetime | None:
    """
    解析时间字段

    :param value: 时间值
    :return:
    """
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _build_model_usage(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    按模型汇总用量

    :param traces: 执行轨迹
    :return:
    """
    usage_map: dict[str, dict[str, Any]] = {}
    for trace in traces:
        model = str(trace.get('model') or '')
        if not model:
            continue
        usage = usage_map.setdefault(
            model,
            {
                'model': model,
                'node_count': 0,
                'duration_ms': 0,
                'tokens_in': 0,
                'tokens_out': 0,
                'tokens_total': 0,
            },
        )
        usage['node_count'] += 1
        usage['duration_ms'] += int(trace.get('duration_ms') or 0)
        usage['tokens_in'] += int(trace.get('tokens_in') or 0)
        usage['tokens_out'] += int(trace.get('tokens_out') or 0)
        usage['tokens_total'] = usage['tokens_in'] + usage['tokens_out']
    return list(usage_map.values())
