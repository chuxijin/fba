#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest

from backend.app.mydrive.service.sync.rules import SyncRule, rename_name, should_exclude, validate_rules
from backend.app.mydrive.service.sync_service import MyDriveSyncService


def test_exclude_rules_support_glob_and_reinclude() -> None:
    """排除规则应支持通配和反向包含。"""
    rules = [SyncRule('exclude', '*.tmp'), SyncRule('exclude', '!keep.tmp')]

    assert should_exclude('course/cache.tmp', False, rules) is True
    assert should_exclude('course/keep.tmp', False, rules) is False


def test_exclude_rules_support_directory_pattern() -> None:
    """目录排除规则只匹配目录。"""
    rules = [SyncRule('exclude', 'node_modules/')]

    assert should_exclude('project/node_modules', True, rules) is True
    assert should_exclude('project/node_modules', False, rules) is False


def test_rename_uses_first_matching_rule() -> None:
    """重命名应只应用首条命中规则。"""
    rules = [SyncRule('rename', r'^\[.*?\]\s*', ''), SyncRule('rename', '课程', '资料')]

    assert rename_name('[公开课] 课程.mp4', rules) == '课程.mp4'


def test_validate_rules_rejects_invalid_regex() -> None:
    """无效重命名正则应被拒绝。"""
    with pytest.raises(ValueError):
        validate_rules([SyncRule('rename', '[')])


def test_rule_values_keep_persistence_fields() -> None:
    """规则持久化字段不应影响规则引擎校验。"""
    values = MyDriveSyncService._get_rule_values(
        [
            SyncRuleParamStub(
                {
                    'is_enabled': True,
                    'pattern': '*.tmp',
                    'replacement': '',
                    'rule_type': 'exclude',
                    'sort_order': 0,
                }
            )
        ]
    )

    assert values[0]['sort_order'] == 0


def test_rename_rejects_path_change() -> None:
    """重命名不能改变目录层级。"""
    with pytest.raises(ValueError):
        rename_name('course.mp4', [SyncRule('rename', 'course', 'folder/course')])


class SyncRuleParamStub:
    """同步规则参数替身。"""

    def __init__(self, value: dict[str, object]) -> None:
        """
        初始化同步规则参数替身。

        :param value: 同步规则字典
        :return:
        """
        self.value = value

    def model_dump(self) -> dict[str, object]:
        """导出同步规则字典。"""
        return self.value
