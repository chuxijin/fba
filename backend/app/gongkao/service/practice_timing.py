from collections.abc import Mapping
from typing import Any


def timing_value(record: Any, key: str, default: Any = None) -> Any:
    return record.get(key, default) if isinstance(record, Mapping) else getattr(record, key, default)


def effective_practice_duration(record: Any, node: Any = None) -> int | None:
    """只使用当前层级已知计时，不覆盖原值，不跨层推算或分配。"""
    if timing_value(record, 'exclude_source_timing', False):
        return timing_value(record if node is None else node, 'manual_duration_seconds')
    return timing_value(record if node is None else node, 'duration_seconds')
