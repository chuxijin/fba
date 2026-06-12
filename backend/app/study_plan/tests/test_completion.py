#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完成判定纯函数真值表测试

覆盖 D10-D12 决策对应的 4 类 module_type 完成规则。
"""
from typing import Any

import pytest

from backend.app.study_plan.service.completion import (
    CompletionCheckResult,
    check_completion,
)


class _StubItem:
    """轻量级 item 替身，仅暴露 module_type / extra"""

    def __init__(self, module_type: str, extra: dict[str, Any] | None = None) -> None:
        self.module_type = module_type
        self.extra = extra


# ============ review ============

class TestReviewCompletion:
    """学习类完成判定"""

    def test_review_without_acknowledge_should_fail(self) -> None:
        result = check_completion(_StubItem('review'), {})
        assert result.ok is False
        assert '已读' in (result.reason or '')

    def test_review_with_acknowledge_false_should_fail(self) -> None:
        result = check_completion(_StubItem('review'), {'read_acknowledged': False})
        assert result.ok is False

    def test_review_with_acknowledge_true_should_pass(self) -> None:
        result = check_completion(_StubItem('review'), {'read_acknowledged': True})
        assert result.ok is True
        assert result.reason is None


# ============ practice ============

class TestPracticeCompletion:
    """刷题类完成判定（D11：题数达标 + 正确率达标）"""

    def test_practice_without_counts_should_fail(self) -> None:
        item = _StubItem('practice', {'question_count': 10, 'required_accuracy': 0.6})
        result = check_completion(item, {})
        assert result.ok is False

    def test_practice_partial_counts_should_fail(self) -> None:
        item = _StubItem('practice', {'question_count': 10, 'required_accuracy': 0.6})
        result = check_completion(item, {'correct_count': 6})
        assert result.ok is False

    def test_practice_unfinished_count_should_fail(self) -> None:
        item = _StubItem('practice', {'question_count': 10, 'required_accuracy': 0.6})
        result = check_completion(item, {'correct_count': 8, 'total_count': 8})
        assert result.ok is False
        assert '8/10' in (result.reason or '')

    def test_practice_low_accuracy_should_fail(self) -> None:
        item = _StubItem('practice', {'question_count': 10, 'required_accuracy': 0.6})
        result = check_completion(item, {'correct_count': 5, 'total_count': 10})
        assert result.ok is False
        assert '正确率' in (result.reason or '')

    def test_practice_meet_accuracy_should_pass(self) -> None:
        item = _StubItem('practice', {'question_count': 10, 'required_accuracy': 0.6})
        result = check_completion(item, {'correct_count': 7, 'total_count': 10})
        assert result.ok is True

    def test_practice_exact_accuracy_should_pass(self) -> None:
        item = _StubItem('practice', {'question_count': 10, 'required_accuracy': 0.6})
        result = check_completion(item, {'correct_count': 6, 'total_count': 10})
        assert result.ok is True

    def test_practice_default_accuracy_06_when_not_set(self) -> None:
        item = _StubItem('practice', {'question_count': 5})
        result = check_completion(item, {'correct_count': 3, 'total_count': 5})
        assert result.ok is True

    def test_practice_with_question_ids_uses_len_as_total(self) -> None:
        item = _StubItem(
            'practice',
            {'question_ids': [1, 2, 3, 4], 'required_accuracy': 0.5},
        )
        result = check_completion(item, {'correct_count': 2, 'total_count': 4})
        assert result.ok is True

    def test_practice_zero_total_should_fail(self) -> None:
        item = _StubItem('practice', {'question_count': 0, 'required_accuracy': 0.6})
        result = check_completion(item, {'correct_count': 0, 'total_count': 0})
        assert result.ok is False


# ============ wrong_review ============

class TestWrongReviewCompletion:
    """错题复盘类完成判定（D12：所有错题填完 reasons + summary）"""

    def test_wrong_review_without_extra_data_should_fail(self) -> None:
        result = check_completion(_StubItem('wrong_review'), {})
        assert result.ok is False
        assert '错题列表' in (result.reason or '')

    def test_wrong_review_empty_expected_should_fail(self) -> None:
        result = check_completion(
            _StubItem('wrong_review'),
            {'extra_data': {'expected_question_ids': [], 'reviewed_question_ids': []}},
        )
        assert result.ok is False

    def test_wrong_review_partial_should_fail(self) -> None:
        result = check_completion(
            _StubItem('wrong_review'),
            {
                'extra_data': {
                    'expected_question_ids': [1, 2, 3],
                    'reviewed_question_ids': [1, 2],
                },
            },
        )
        assert result.ok is False
        assert '1' in (result.reason or '')

    def test_wrong_review_full_match_should_pass(self) -> None:
        result = check_completion(
            _StubItem('wrong_review'),
            {
                'extra_data': {
                    'expected_question_ids': [1, 2, 3],
                    'reviewed_question_ids': [3, 1, 2],
                },
            },
        )
        assert result.ok is True

    def test_wrong_review_extra_reviewed_ok(self) -> None:
        """已 review 的多于 expected 不应报错"""
        result = check_completion(
            _StubItem('wrong_review'),
            {
                'extra_data': {
                    'expected_question_ids': [1, 2],
                    'reviewed_question_ids': [1, 2, 99],
                },
            },
        )
        assert result.ok is True


# ============ ability ============

class TestAbilityCompletion:
    """能力提升类完成判定"""

    def test_ability_without_target_should_pass(self) -> None:
        result = check_completion(_StubItem('ability'), {})
        assert result.ok is True

    def test_ability_with_target_without_counts_should_fail(self) -> None:
        item = _StubItem('ability', {'question_count': 10, 'required_accuracy': 0.7})
        result = check_completion(item, {})
        assert result.ok is False

    def test_ability_unfinished_count_should_fail(self) -> None:
        item = _StubItem('ability', {'question_count': 10, 'required_accuracy': 0.7})
        result = check_completion(item, {'correct_count': 8, 'total_count': 8})
        assert result.ok is False
        assert '8/10' in (result.reason or '')

    def test_ability_low_accuracy_should_fail(self) -> None:
        item = _StubItem('ability', {'question_count': 10, 'required_accuracy': 0.7})
        result = check_completion(item, {'correct_count': 6, 'total_count': 10})
        assert result.ok is False
        assert '正确率' in (result.reason or '')

    def test_ability_meet_target_should_pass(self) -> None:
        item = _StubItem('ability', {'question_count': 10, 'required_accuracy': 0.7})
        result = check_completion(item, {'correct_count': 7, 'total_count': 10})
        assert result.ok is True


# ============ unknown ============

class TestUnknownModuleType:
    """未知模块类型应被识别"""

    def test_unknown_type_should_fail(self) -> None:
        result = check_completion(_StubItem('xxx'), {})
        assert result.ok is False
        assert '未知模块类型' in (result.reason or '')


# ============ result helpers ============

class TestCompletionCheckResult:
    """CompletionCheckResult 工厂方法"""

    def test_pass_factory(self) -> None:
        r = CompletionCheckResult.pass_()
        assert r.ok is True
        assert r.reason is None

    def test_fail_factory(self) -> None:
        r = CompletionCheckResult.fail('reason 1')
        assert r.ok is False
        assert r.reason == 'reason 1'
