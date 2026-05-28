"""配置模块"""

from backend.plugin.oc.config.formatter import (
    FORMATTER_CONFIG,
    parse_resume_key,
    get_field_mapping,
    find_best_match,
)

__all__ = [
    'FORMATTER_CONFIG',
    'parse_resume_key',
    'get_field_mapping',
    'find_best_match',
]
