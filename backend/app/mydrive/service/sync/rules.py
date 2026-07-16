#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True, slots=True)
class SyncRule:
    """文件同步规则。"""

    rule_type: str
    pattern: str
    replacement: str = ''
    is_enabled: bool = True


def should_exclude(path: str, is_directory: bool, rules: list[SyncRule]) -> bool:
    """按 Gitignore 风格判断是否排除路径。"""
    excluded = False
    normalized_path = path.strip('/')
    for rule in rules:
        if not rule.is_enabled or rule.rule_type != 'exclude':
            continue
        pattern = rule.pattern.strip()
        if not pattern or pattern.startswith('#'):
            continue
        include = pattern.startswith('!')
        if include:
            pattern = pattern[1:]
        if _matches_glob(normalized_path, is_directory, pattern):
            excluded = not include
    return excluded


def rename_name(name: str, rules: list[SyncRule]) -> str:
    """按顺序应用首条命中的重命名规则。"""
    for rule in rules:
        if not rule.is_enabled or rule.rule_type != 'rename':
            continue
        renamed_name, count = re.subn(rule.pattern, rule.replacement, name)
        if count:
            _validate_renamed_name(renamed_name)
            return renamed_name
    return name


def validate_rules(rules: list[SyncRule]) -> None:
    """验证同步规则表达式。"""
    for rule in rules:
        if rule.rule_type not in {'exclude', 'rename'}:
            raise ValueError(f'不支持的同步规则类型: {rule.rule_type}')
        if not rule.pattern.strip():
            raise ValueError('同步规则匹配表达式不能为空')
        if rule.rule_type == 'rename':
            try:
                re.compile(rule.pattern)
                _validate_renamed_name(re.sub(rule.pattern, rule.replacement, 'sync-name'))
            except re.PatternError as exc:
                raise ValueError(f'重命名正则表达式无效: {exc}') from exc


def _matches_glob(path: str, is_directory: bool, pattern: str) -> bool:
    """按 Gitignore 常用约定匹配相对路径。"""
    directory_only = pattern.endswith('/')
    if directory_only:
        pattern = pattern.rstrip('/')
        if not is_directory:
            return False
    anchored = pattern.startswith('/')
    pattern = pattern.lstrip('/')
    if not pattern:
        return False
    if anchored or '/' in pattern:
        return fnmatch.fnmatchcase(path, pattern)
    return any(fnmatch.fnmatchcase(part, pattern) for part in PurePosixPath(path).parts)


def _validate_renamed_name(name: str) -> None:
    """验证重命名后的文件名称。"""
    if not name or name in {'.', '..'} or '/' in name or '\\' in name:
        raise ValueError('重命名结果必须是有效的单层文件名称')
