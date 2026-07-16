#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import importlib

from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.app.challenge.schema.challenge import (
    ChallengeAnswerItem,
    ChallengeCompletionRuleParam,
    ChallengeLevelParam,
    ChallengeSectionParam,
    SubmitChallengeAttemptParam,
    UpdateChallengeLevelParam,
)
from backend.app.challenge.service.generator import generate_challenge_question
from backend.app.challenge.service.challenge_service import challenge_service
from backend.app.question_bank.service.question_service import question_service
from backend.common.exception import errors

challenge_service_module = importlib.import_module('backend.app.challenge.service.challenge_service')


def run(coro):
    """同步执行协程"""
    return asyncio.new_event_loop().run_until_complete(coro)


def build_sections() -> list[ChallengeSectionParam]:
    """构建基础分组配置"""
    return [
        ChallengeSectionParam(
            seq_no=1,
            name='基础计算',
            source_type='generator',
            question_count=2,
            source_config={'generator_key': 'data_analysis_growth_rate_v1'},
            required_correct_count=1,
            enabled=True,
        ),
        ChallengeSectionParam(
            seq_no=2,
            name='综合判断',
            source_type='generator',
            question_count=1,
            source_config={'generator_key': 'data_analysis_base_value_v1'},
            required_correct_count=1,
            enabled=True,
        ),
    ]


def build_level_model(
    *,
    description: str | None = '原始描述',
    previous_level_id: int | None = 99,
    display_config: dict[str, object] | None = None,
    status: str = 'published',
    config_version: int = 1,
):
    """构建关卡模型桩对象"""
    return SimpleNamespace(
        id=1,
        challenge_key='data_analysis',
        stage='stage_1',
        level_no=1,
        global_no=1,
        title='第 1 关',
        description=description,
        previous_level_id=previous_level_id,
        question_count=3,
        time_limit=120,
        pass_rate=Decimal('80'),
        star_two_rate=Decimal('90'),
        star_three_rate=Decimal('100'),
        required_section_pass=False,
        display_config=display_config,
        status=status,
        config_version=config_version,
        sort_order=1,
        sections=[
            SimpleNamespace(
                id=11,
                seq_no=1,
                name='基础计算',
                source_type='generator',
                question_count=2,
                source_config={'generator_key': 'data_analysis_growth_rate_v1'},
                required_correct_count=1,
                enabled=True,
            ),
            SimpleNamespace(
                id=12,
                seq_no=2,
                name='综合判断',
                source_type='generator',
                question_count=1,
                source_config={'generator_key': 'data_analysis_base_value_v1'},
                required_correct_count=1,
                enabled=True,
            ),
        ],
    )


def test_validate_level_config_rejects_question_count_mismatch() -> None:
    """启用分组题量与关卡题量不一致时应拒绝"""
    obj = ChallengeLevelParam(
        challenge_key='data_analysis',
        stage='stage_1',
        level_no=1,
        global_no=1,
        title='第 1 关',
        question_count=4,
        time_limit=120,
        pass_rate=Decimal('80'),
        star_two_rate=Decimal('90'),
        star_three_rate=Decimal('100'),
        required_section_pass=False,
        sections=build_sections(),
    )

    with pytest.raises(errors.RequestError, match='启用分组题量合计为 3'):
        challenge_service._validate_level_config(obj)


def test_update_level_allows_clearing_nullable_fields(monkeypatch) -> None:
    """更新关卡时应允许显式清空可空字段"""
    level_before = build_level_model(display_config={'theme': 'storm'})
    level_after = build_level_model(
        description=None,
        previous_level_id=None,
        display_config=None,
        status='draft',
        config_version=2,
    )
    call_state = {'count': 0}
    captured_update: dict[str, object] = {}

    async def fake_get_with_sections(_db, _level_id):
        call_state['count'] += 1
        if call_state['count'] == 1:
            return level_before
        return level_after

    async def fake_update(_db, _level_id, data):
        captured_update.update(data)
        return 1

    monkeypatch.setattr(challenge_service_module.challenge_level_dao, 'get_with_sections', fake_get_with_sections)
    monkeypatch.setattr(challenge_service_module.challenge_level_dao, 'update', fake_update)

    result = run(
        challenge_service.update_level(
            db=None,
            level_id=1,
            obj=UpdateChallengeLevelParam(
                description=None,
                previous_level_id=None,
                display_config=None,
            ),
            user_id=7,
        )
    )

    assert captured_update['description'] is None
    assert captured_update['previous_level_id'] is None
    assert captured_update['display_config'] is None
    assert captured_update['status'] == 'draft'
    assert captured_update['config_version'] == 2
    assert result.description is None
    assert result.previous_level_id is None
    assert result.display_config is None
    assert result.status == 'draft'


def test_submit_attempt_requires_section_pass_before_unlock(monkeypatch) -> None:
    """总正确率达标但分组未达标时不应通关"""
    runtime = {
        'questions': [
            {
                'seq_no': 1,
                'section_seq': 1,
                'type': 'single',
                'answer_data': {'correct': 'A'},
                'analysis': '题 1 解析',
            },
            {
                'seq_no': 2,
                'section_seq': 1,
                'type': 'single',
                'answer_data': {'correct': 'B'},
                'analysis': '题 2 解析',
            },
            {
                'seq_no': 3,
                'section_seq': 2,
                'type': 'single',
                'answer_data': {'correct': 'C'},
                'analysis': '题 3 解析',
            },
        ]
    }
    attempt = SimpleNamespace(
        id=501,
        attempt_key='attempt-key-1',
        user_id=9,
        level_id=88,
        status='in_progress',
        rule_snapshot={
            'pass_rate': '50',
            'star_two_rate': '80',
            'star_three_rate': '100',
            'required_section_pass': True,
            'sections': [
                {'seq_no': 1, 'required_correct_count': 2},
                {'seq_no': 2, 'required_correct_count': 1},
            ],
        },
    )
    current_level = SimpleNamespace(id=88, challenge_key='data_analysis', global_no=7)
    next_level = SimpleNamespace(id=89)
    captured_update: dict[str, object] = {}
    captured_progress: dict[str, object] = {}
    deleted_keys: list[str] = []

    async def fake_get_by_key(_db, _attempt_key, *, for_update=False):
        return attempt

    async def fake_update(_db, _attempt_id, data):
        captured_update.update(data)
        return 1

    async def fake_load_runtime(_attempt_key):
        return runtime, 600

    async def fake_update_progress(**kwargs):
        captured_progress.update(kwargs)
        return None

    async def fake_get_level(_db, _level_id):
        return current_level

    async def fake_get_next_level(_db, _challenge_key, _global_no):
        return next_level

    async def fake_delete(key):
        deleted_keys.append(key)
        return None

    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'get_by_key', fake_get_by_key)
    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'update', fake_update)
    monkeypatch.setattr(challenge_service_module.challenge_level_dao, 'get', fake_get_level)
    monkeypatch.setattr(challenge_service_module.challenge_level_dao, 'get_by_global_no', fake_get_next_level)
    monkeypatch.setattr(challenge_service, '_load_runtime', fake_load_runtime)
    monkeypatch.setattr(challenge_service, '_update_progress', fake_update_progress)
    monkeypatch.setattr(challenge_service_module.redis_client, 'delete', fake_delete)

    result = run(
        challenge_service.submit_attempt(
            db=None,
            user_id=9,
            attempt_key='attempt-key-1',
            obj=SubmitChallengeAttemptParam(
                answers=[
                    ChallengeAnswerItem(seq_no=1, user_answer='A', answer_time=6),
                    ChallengeAnswerItem(seq_no=2, user_answer='D', answer_time=7),
                    ChallengeAnswerItem(seq_no=3, user_answer='C', answer_time=8),
                ],
                total_time=99,
            ),
        )
    )

    assert result.passed is False
    assert result.stars == 0
    assert result.accuracy_rate == Decimal('66.67')
    assert result.next_level_id == 89
    assert result.next_level_unlocked is False
    assert captured_update['passed'] is False
    assert captured_update['stars'] == 0
    assert captured_update['accuracy_rate'] == Decimal('66.67')
    assert captured_progress['passed'] is False
    assert captured_progress['stars'] == 0
    assert deleted_keys == ['challenge:attempt:attempt-key-1']


def build_consecutive_rule_snapshot(required_attempts: int = 5) -> dict[str, object]:
    """构建连续达标通关规则快照"""
    return {
        'pass_rate': '100',
        'star_two_rate': '100',
        'star_three_rate': '100',
        'required_section_pass': False,
        'completion_rule': {
            'mode': 'consecutive_attempts',
            'required_attempts': required_attempts,
            'min_accuracy_rate': '100',
            'max_total_time': 50,
        },
        'sections': [],
    }


def build_varying_consecutive_rule_snapshot() -> dict[str, object]:
    """构建差异化连续达标通关规则快照"""
    return {
        'pass_rate': '75',
        'star_two_rate': '100',
        'star_three_rate': '100',
        'required_section_pass': False,
        'completion_rule': {
            'mode': 'consecutive_attempts',
            'required_attempts': 5,
            'min_accuracy_rate': '75',
            'max_total_time': 120,
            'attempt_requirements': [
                {
                    'seq_no': 1,
                    'title': '第一次',
                    'min_accuracy_rate': '75',
                    'max_total_time': 120,
                },
                {
                    'seq_no': 2,
                    'title': '第二次',
                    'min_accuracy_rate': '100',
                    'max_total_time': 120,
                },
            ],
        },
        'current_attempt_index': 2,
        'current_attempt_requirement': {
            'seq_no': 2,
            'title': '第二次',
            'min_accuracy_rate': '100',
            'max_total_time': 120,
        },
        'sections': [],
    }


def test_validate_level_config_rejects_invalid_consecutive_rule() -> None:
    """连续达标模式要求次数不能小于 2"""
    obj = ChallengeLevelParam(
        challenge_key='data_analysis',
        stage='stage_1',
        level_no=1,
        global_no=1,
        title='第 1 关',
        question_count=3,
        time_limit=120,
        pass_rate=Decimal('80'),
        star_two_rate=Decimal('90'),
        star_three_rate=Decimal('100'),
        required_section_pass=False,
        completion_rule=ChallengeCompletionRuleParam(
            mode='consecutive_attempts',
            required_attempts=1,
            min_accuracy_rate=Decimal('100'),
            max_total_time=50,
        ),
        sections=build_sections(),
    )

    with pytest.raises(errors.RequestError, match='连续达标模式的要求达标次数不能小于 2'):
        challenge_service._validate_level_config(obj)


def test_submit_attempt_uses_current_varying_requirement(monkeypatch) -> None:
    """连续达标应按当前序号使用差异化要求"""
    runtime = {
        'questions': [
            {
                'seq_no': 1,
                'section_seq': 1,
                'type': 'single',
                'answer_data': {'correct': 'A'},
                'analysis': '解析 1',
            },
            {
                'seq_no': 2,
                'section_seq': 1,
                'type': 'single',
                'answer_data': {'correct': 'B'},
                'analysis': '解析 2',
            },
            {
                'seq_no': 3,
                'section_seq': 1,
                'type': 'single',
                'answer_data': {'correct': 'C'},
                'analysis': '解析 3',
            },
            {
                'seq_no': 4,
                'section_seq': 1,
                'type': 'single',
                'answer_data': {'correct': 'D'},
                'analysis': '解析 4',
            },
        ]
    }
    attempt = SimpleNamespace(
        id=604,
        attempt_key='attempt-key-varying',
        user_id=9,
        level_id=88,
        status='in_progress',
        rule_snapshot=build_varying_consecutive_rule_snapshot(),
    )
    current_level = SimpleNamespace(id=88, challenge_key='data_analysis', global_no=7)
    next_level = SimpleNamespace(id=89)
    updates: list[dict[str, object]] = []

    async def fake_get_by_key(_db, _attempt_key, *, for_update=False):
        return attempt

    async def fake_update(_db, _attempt_id, data):
        updates.append(data.copy())
        return 1

    async def fake_get_recent_completed(_db, _user_id, _level_id, _limit):
        raise AssertionError('当前差异化要求未达标时不应查询连续记录')

    async def fake_load_runtime(_attempt_key):
        return runtime, 600

    async def fake_update_progress(**kwargs):
        return SimpleNamespace(passed=kwargs['passed'])

    async def fake_get_level(_db, _level_id):
        return current_level

    async def fake_get_next_level(_db, _challenge_key, _global_no):
        return next_level

    async def fake_delete(_key):
        return None

    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'get_by_key', fake_get_by_key)
    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'update', fake_update)
    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'get_recent_completed', fake_get_recent_completed)
    monkeypatch.setattr(challenge_service_module.challenge_level_dao, 'get', fake_get_level)
    monkeypatch.setattr(challenge_service_module.challenge_level_dao, 'get_by_global_no', fake_get_next_level)
    monkeypatch.setattr(challenge_service, '_load_runtime', fake_load_runtime)
    monkeypatch.setattr(challenge_service, '_update_progress', fake_update_progress)
    monkeypatch.setattr(challenge_service_module.redis_client, 'delete', fake_delete)

    result = run(
        challenge_service.submit_attempt(
            db=None,
            user_id=9,
            attempt_key='attempt-key-varying',
            obj=SubmitChallengeAttemptParam(
                answers=[
                    ChallengeAnswerItem(seq_no=1, user_answer='A', answer_time=10),
                    ChallengeAnswerItem(seq_no=2, user_answer='B', answer_time=10),
                    ChallengeAnswerItem(seq_no=3, user_answer='C', answer_time=10),
                    ChallengeAnswerItem(seq_no=4, user_answer='A', answer_time=10),
                ],
                total_time=40,
            ),
        )
    )

    assert result.current_attempt_qualified is False
    assert result.current_attempt_index == 2
    assert result.current_attempt_requirement is not None
    assert result.current_attempt_requirement.min_accuracy_rate == Decimal('100')
    assert result.qualified_attempts == 0
    assert updates[0]['passed'] is False


def test_submit_attempt_keeps_locked_before_required_consecutive_attempts(monkeypatch) -> None:
    """连续达标未满要求次数时不应解锁下一关"""
    runtime = {
        'questions': [
            {
                'seq_no': 1,
                'section_seq': 1,
                'type': 'single',
                'answer_data': {'correct': 'A'},
                'analysis': '解析',
            }
        ]
    }
    attempt = SimpleNamespace(
        id=601,
        attempt_key='attempt-key-2',
        user_id=9,
        level_id=88,
        status='in_progress',
        rule_snapshot=build_consecutive_rule_snapshot(),
    )
    current_level = SimpleNamespace(id=88, challenge_key='data_analysis', global_no=7)
    next_level = SimpleNamespace(id=89)
    updates: list[dict[str, object]] = []
    captured_progress: dict[str, object] = {}

    async def fake_get_by_key(_db, _attempt_key, *, for_update=False):
        return attempt

    async def fake_update(_db, _attempt_id, data):
        updates.append(data.copy())
        return 1

    async def fake_get_recent_completed(_db, _user_id, _level_id, _limit):
        return [
            attempt,
            SimpleNamespace(passed=True),
            SimpleNamespace(passed=True),
            SimpleNamespace(passed=True),
        ]

    async def fake_load_runtime(_attempt_key):
        return runtime, 600

    async def fake_update_progress(**kwargs):
        captured_progress.update(kwargs)
        return SimpleNamespace(passed=kwargs['passed'])

    async def fake_get_level(_db, _level_id):
        return current_level

    async def fake_get_next_level(_db, _challenge_key, _global_no):
        return next_level

    async def fake_delete(_key):
        return None

    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'get_by_key', fake_get_by_key)
    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'update', fake_update)
    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'get_recent_completed', fake_get_recent_completed)
    monkeypatch.setattr(challenge_service_module.challenge_level_dao, 'get', fake_get_level)
    monkeypatch.setattr(challenge_service_module.challenge_level_dao, 'get_by_global_no', fake_get_next_level)
    monkeypatch.setattr(challenge_service, '_load_runtime', fake_load_runtime)
    monkeypatch.setattr(challenge_service, '_update_progress', fake_update_progress)
    monkeypatch.setattr(challenge_service_module.redis_client, 'delete', fake_delete)

    result = run(
        challenge_service.submit_attempt(
            db=None,
            user_id=9,
            attempt_key='attempt-key-2',
            obj=SubmitChallengeAttemptParam(
                answers=[ChallengeAnswerItem(seq_no=1, user_answer='A', answer_time=10)],
                total_time=50,
            ),
        )
    )

    assert result.current_attempt_qualified is True
    assert result.qualified_attempts == 4
    assert result.required_attempts == 5
    assert result.passed is False
    assert result.next_level_unlocked is False
    assert updates[0]['passed'] is True
    assert captured_progress['passed'] is False


def test_submit_attempt_unlocks_after_required_consecutive_attempts(monkeypatch) -> None:
    """连续达标满要求次数时应解锁下一关"""
    runtime = {
        'questions': [
            {
                'seq_no': 1,
                'section_seq': 1,
                'type': 'single',
                'answer_data': {'correct': 'A'},
                'analysis': '解析',
            }
        ]
    }
    attempt = SimpleNamespace(
        id=602,
        attempt_key='attempt-key-3',
        user_id=9,
        level_id=88,
        status='in_progress',
        rule_snapshot=build_consecutive_rule_snapshot(),
    )
    current_level = SimpleNamespace(id=88, challenge_key='data_analysis', global_no=7)
    next_level = SimpleNamespace(id=89)
    updates: list[dict[str, object]] = []
    captured_progress: dict[str, object] = {}

    async def fake_get_by_key(_db, _attempt_key, *, for_update=False):
        return attempt

    async def fake_update(_db, _attempt_id, data):
        updates.append(data.copy())
        return 1

    async def fake_get_recent_completed(_db, _user_id, _level_id, _limit):
        return [
            attempt,
            SimpleNamespace(passed=True),
            SimpleNamespace(passed=True),
            SimpleNamespace(passed=True),
            SimpleNamespace(passed=True),
        ]

    async def fake_load_runtime(_attempt_key):
        return runtime, 600

    async def fake_update_progress(**kwargs):
        captured_progress.update(kwargs)
        return SimpleNamespace(passed=kwargs['passed'])

    async def fake_get_level(_db, _level_id):
        return current_level

    async def fake_get_next_level(_db, _challenge_key, _global_no):
        return next_level

    async def fake_delete(_key):
        return None

    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'get_by_key', fake_get_by_key)
    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'update', fake_update)
    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'get_recent_completed', fake_get_recent_completed)
    monkeypatch.setattr(challenge_service_module.challenge_level_dao, 'get', fake_get_level)
    monkeypatch.setattr(challenge_service_module.challenge_level_dao, 'get_by_global_no', fake_get_next_level)
    monkeypatch.setattr(challenge_service, '_load_runtime', fake_load_runtime)
    monkeypatch.setattr(challenge_service, '_update_progress', fake_update_progress)
    monkeypatch.setattr(challenge_service_module.redis_client, 'delete', fake_delete)

    result = run(
        challenge_service.submit_attempt(
            db=None,
            user_id=9,
            attempt_key='attempt-key-3',
            obj=SubmitChallengeAttemptParam(
                answers=[ChallengeAnswerItem(seq_no=1, user_answer='A', answer_time=10)],
                total_time=50,
            ),
        )
    )

    assert result.current_attempt_qualified is True
    assert result.qualified_attempts == 5
    assert result.required_attempts == 5
    assert result.passed is True
    assert result.next_level_unlocked is True
    assert updates[0]['passed'] is True
    assert captured_progress['passed'] is True


def test_submit_attempt_rejects_consecutive_qualification_when_time_exceeded(monkeypatch) -> None:
    """超过通关用时上限时本次不算达标"""
    runtime = {
        'questions': [
            {
                'seq_no': 1,
                'section_seq': 1,
                'type': 'single',
                'answer_data': {'correct': 'A'},
                'analysis': '解析',
            }
        ]
    }
    attempt = SimpleNamespace(
        id=603,
        attempt_key='attempt-key-4',
        user_id=9,
        level_id=88,
        status='in_progress',
        rule_snapshot=build_consecutive_rule_snapshot(),
    )
    current_level = SimpleNamespace(id=88, challenge_key='data_analysis', global_no=7)
    next_level = SimpleNamespace(id=89)
    updates: list[dict[str, object]] = []

    async def fake_get_by_key(_db, _attempt_key, *, for_update=False):
        return attempt

    async def fake_update(_db, _attempt_id, data):
        updates.append(data.copy())
        return 1

    async def fake_get_recent_completed(_db, _user_id, _level_id, _limit):
        raise AssertionError('本次未达标时不应查询连续记录')

    async def fake_load_runtime(_attempt_key):
        return runtime, 600

    async def fake_update_progress(**kwargs):
        return SimpleNamespace(passed=kwargs['passed'])

    async def fake_get_level(_db, _level_id):
        return current_level

    async def fake_get_next_level(_db, _challenge_key, _global_no):
        return next_level

    async def fake_delete(_key):
        return None

    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'get_by_key', fake_get_by_key)
    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'update', fake_update)
    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'get_recent_completed', fake_get_recent_completed)
    monkeypatch.setattr(challenge_service_module.challenge_level_dao, 'get', fake_get_level)
    monkeypatch.setattr(challenge_service_module.challenge_level_dao, 'get_by_global_no', fake_get_next_level)
    monkeypatch.setattr(challenge_service, '_load_runtime', fake_load_runtime)
    monkeypatch.setattr(challenge_service, '_update_progress', fake_update_progress)
    monkeypatch.setattr(challenge_service_module.redis_client, 'delete', fake_delete)

    result = run(
        challenge_service.submit_attempt(
            db=None,
            user_id=9,
            attempt_key='attempt-key-4',
            obj=SubmitChallengeAttemptParam(
                answers=[ChallengeAnswerItem(seq_no=1, user_answer='A', answer_time=10)],
                total_time=51,
            ),
        )
    )

    assert result.current_attempt_qualified is False
    assert result.qualified_attempts == 0
    assert result.required_attempts == 5
    assert result.passed is False
    assert result.next_level_unlocked is False
    assert updates[0]['passed'] is False


def test_submit_attempt_supports_matching_question(monkeypatch) -> None:
    """匹配题应支持结构化答案判题"""
    runtime = {
        'questions': [
            {
                'seq_no': 1,
                'section_seq': 1,
                'type': 'matching',
                'stem': '请将城市与省份匹配',
                'interaction_config': {
                    'left_items': [
                        {'id': 'hangzhou', 'content': '杭州'},
                        {'id': 'nanjing', 'content': '南京'},
                    ],
                    'right_items': [
                        {'id': 'zhejiang', 'content': '浙江'},
                        {'id': 'jiangsu', 'content': '江苏'},
                    ],
                },
                'answer_data': {
                    'correct': {
                        'hangzhou': 'zhejiang',
                        'nanjing': 'jiangsu',
                    }
                },
                'analysis': '杭州对应浙江，南京对应江苏。',
            }
        ]
    }
    attempt = SimpleNamespace(
        id=701,
        attempt_key='attempt-key-5',
        user_id=9,
        level_id=88,
        status='in_progress',
        rule_snapshot={
            'pass_rate': '100',
            'star_two_rate': '100',
            'star_three_rate': '100',
            'required_section_pass': False,
            'sections': [],
        },
    )
    current_level = SimpleNamespace(id=88, challenge_key='data_analysis', global_no=7)
    next_level = SimpleNamespace(id=89)

    async def fake_get_by_key(_db, _attempt_key, *, for_update=False):
        return attempt

    async def fake_update(_db, _attempt_id, data):
        return 1

    async def fake_load_runtime(_attempt_key):
        return runtime, 600

    async def fake_update_progress(**kwargs):
        return SimpleNamespace(passed=kwargs['passed'])

    async def fake_get_level(_db, _level_id):
        return current_level

    async def fake_get_next_level(_db, _challenge_key, _global_no):
        return next_level

    async def fake_delete(_key):
        return None

    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'get_by_key', fake_get_by_key)
    monkeypatch.setattr(challenge_service_module.challenge_attempt_dao, 'update', fake_update)
    monkeypatch.setattr(challenge_service_module.challenge_level_dao, 'get', fake_get_level)
    monkeypatch.setattr(challenge_service_module.challenge_level_dao, 'get_by_global_no', fake_get_next_level)
    monkeypatch.setattr(challenge_service, '_load_runtime', fake_load_runtime)
    monkeypatch.setattr(challenge_service, '_update_progress', fake_update_progress)
    monkeypatch.setattr(challenge_service_module.redis_client, 'delete', fake_delete)

    result = run(
        challenge_service.submit_attempt(
            db=None,
            user_id=9,
            attempt_key='attempt-key-5',
            obj=SubmitChallengeAttemptParam(
                answers=[
                    ChallengeAnswerItem(
                        seq_no=1,
                        user_answer={
                            'hangzhou': 'zhejiang',
                            'nanjing': 'jiangsu',
                        },
                        answer_time=10,
                    )
                ],
                total_time=30,
            ),
        )
    )

    assert result.current_attempt_qualified is True
    assert result.passed is True
    assert result.correct_count == 1
    assert result.results[0].is_correct is True
    assert result.results[0].correct_answer == {'hangzhou': 'zhejiang', 'nanjing': 'jiangsu'}


def test_public_question_returns_interaction_config() -> None:
    """公开题目应返回交互配置但不返回答案数据"""
    item = {
        'seq_no': 1,
        'section_seq': 1,
        'type': 'matching',
        'stem': '请匹配',
        'material': None,
        'options': [],
        'interaction_config': {
            'left_items': [{'id': 'left_1', 'content': '左 1'}],
            'right_items': [{'id': 'right_1', 'content': '右 1'}],
        },
        'answer_data': {'correct': {'left_1': 'right_1'}},
    }

    result = challenge_service._public_question(item)

    assert result.type == 'matching'
    assert result.interaction_config == {
        'left_items': [{'id': 'left_1', 'content': '左 1'}],
        'right_items': [{'id': 'right_1', 'content': '右 1'}],
    }


def test_generate_data_analysis_concept_identification_question() -> None:
    """资料分析概念识别生成器应生成单选题"""
    question = generate_challenge_question(
        generator_key='data_analysis_concept_matching_v1',
        stage='stage_1',
        params={
            'unit': '亿元',
            'subject': '全市文旅收入',
            'current_year': 2026,
            'current_month': 6,
        },
    )

    correct_answer = question['answer_data']['correct']
    option_codes = {item['option_code'] for item in question['options']}
    option_contents = {item['content'] for item in question['options']}
    concept_names = {'基期值', '现期值', '增长量', '变化量', '变化幅度', '增长率', '同比', '环比'}

    assert question['type'] == 'single'
    assert '属于什么概念' in question['stem']
    assert question['material'] is None
    assert '资料：' not in question['stem']
    assert '概念定义：' not in question['stem']
    assert '概念提示' not in question['stem']
    assert len(question['options']) == 4
    assert correct_answer in option_codes
    assert option_contents <= concept_names
    assert question_service.check_answer('single', correct_answer, question['answer_data']) is True


def test_generate_data_analysis_concept_identification_alias_question() -> None:
    """概念识别新生成器标识应可用"""
    question = generate_challenge_question(
        generator_key='data_analysis_concept_identification_v1',
        stage='stage_1',
    )

    assert question['type'] == 'single'
    assert '属于什么概念' in question['stem']


def test_generate_data_analysis_concept_identification_can_limit_concepts() -> None:
    """概念识别生成器应支持限定四个基础概念"""
    concept_ids = ['base_value', 'current_value', 'growth_rate', 'growth_amount']
    question = generate_challenge_question(
        generator_key='data_analysis_concept_identification_v1',
        stage='stage_1',
        params={
            'concept_ids': concept_ids,
            'question_index': 2,
        },
    )

    option_contents = {item['content'] for item in question['options']}

    assert question['type'] == 'single'
    assert len(question['options']) == 4
    assert option_contents == {'基期值', '现期值', '增长率', '增长量'}
    assert question['material'] is None
    assert '变化量：' not in question['stem']
    assert '同比：' not in question['stem']
    assert '环比：' not in question['stem']


def test_generate_data_analysis_second_level_concepts_are_balanced() -> None:
    """第二关概念识别应平均覆盖比较口径与变化表达"""
    concept_ids = ['yoy', 'mom', 'change_amount', 'change_rate']
    answer_names: list[str] = []
    stems: list[str] = []

    for question_index in range(8):
        question = generate_challenge_question(
            generator_key='data_analysis_concept_identification_v1',
        stage='stage_1',
            params={
                'concept_ids': concept_ids,
                'question_index': question_index,
                'question_count': 8,
            },
        )
        correct_code = question['answer_data']['correct']
        correct_option = next(item for item in question['options'] if item['option_code'] == correct_code)
        answer_names.append(correct_option['content'])
        stems.append(question['stem'])

        option_contents = {item['content'] for item in question['options']}
        assert option_contents == {'同比', '环比', '变化量', '变化幅度'}
        assert '基期值' not in question['stem']
        assert '现期值' not in question['stem']
        assert '增长率' not in question['stem']
        assert '增长量' not in question['stem']

    assert answer_names.count('同比') == 2
    assert answer_names.count('环比') == 2
    assert answer_names.count('变化量') == 2
    assert answer_names.count('变化幅度') == 2
    assert len(set(stems)) == 8
