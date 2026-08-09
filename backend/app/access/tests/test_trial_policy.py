#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

import pytest

from backend.app.access.constants import GrantMode, ReasonCode, TrialMode
from backend.app.access.engine.evaluators.trial_policy import TrialPolicyEvaluator
from backend.app.access.tests.conftest import FakeSnapshot, make_ctx, make_rule


def _run(ctx, rules, explanation, snapshot: FakeSnapshot):
    """执行试看评估器"""
    return asyncio.run(TrialPolicyEvaluator().evaluate(None, ctx, rules, snapshot, explanation))


def test_trial_skipped_when_business_disallows(empty_snapshot: FakeSnapshot) -> None:
    """业务方禁用试看时直接让出, 不做任何判定"""
    explanation: list = []
    rules = [make_rule(GrantMode.ACCESS, trial_policy={'mode': 'ordinal', 'limit': 5})]

    decision = _run(make_ctx(allow_trial=False), rules, explanation, empty_snapshot)

    assert decision is None
    assert explanation[-1].reason == '当前业务不允许试看'


def test_trial_passes_when_no_policy_configured(empty_snapshot: FakeSnapshot) -> None:
    """资源未配置试看策略时让出给最终 deny"""
    explanation: list = []
    rules = [make_rule(GrantMode.ACCESS)]

    decision = _run(make_ctx(), rules, explanation, empty_snapshot)

    assert decision is None
    assert explanation[-1].reason == '资源未配置试看策略'


@pytest.mark.parametrize(
    ('ordinal', 'allowed'),
    [(0, True), (4, True), (5, False), (12, False)],
)
def test_ordinal_trial_allows_first_n(empty_snapshot: FakeSnapshot, ordinal: int, allowed: bool) -> None:
    """按量试刷: 前 5 道题免费, 第 6 道起拒绝"""
    explanation: list = []
    rules = [make_rule(GrantMode.ACCESS, trial_policy={'mode': 'ordinal', 'limit': 5})]

    decision = _run(make_ctx(sub_resource_ordinal=ordinal), rules, explanation, empty_snapshot)

    assert decision is not None
    assert decision.allowed is allowed
    if allowed:
        assert decision.reason_code == ReasonCode.TRIAL_POLICY
        assert decision.trial_mode == TrialMode.ORDINAL
    else:
        assert decision.reason_code == ReasonCode.TRIAL_EXHAUSTED


def test_ordinal_trial_skipped_without_ordinal_context(empty_snapshot: FakeSnapshot) -> None:
    """业务层没提供序号时无法判定, 让出而不是误放行"""
    explanation: list = []
    rules = [make_rule(GrantMode.ACCESS, trial_policy={'mode': 'ordinal', 'limit': 5})]

    decision = _run(make_ctx(), rules, explanation, empty_snapshot)

    assert decision is None
    assert explanation[-1].reason == '试看策略缺少判定所需的上下文'


@pytest.mark.parametrize(
    ('ordinal', 'allowed'),
    [(0, True), (9, True), (10, False)],
)
def test_fraction_trial_allows_leading_ratio(
    empty_snapshot: FakeSnapshot,
    ordinal: int,
    allowed: bool,
) -> None:
    """按比例试看: 100 题里前 10% 免费"""
    explanation: list = []
    rules = [make_rule(GrantMode.ACCESS, trial_policy={'mode': 'fraction', 'ratio': 0.1})]

    decision = _run(
        make_ctx(sub_resource_ordinal=ordinal, sub_resource_total=100),
        rules,
        explanation,
        empty_snapshot,
    )

    assert decision is not None
    assert decision.allowed is allowed


def test_excerpt_trial_allows_with_char_budget(empty_snapshot: FakeSnapshot) -> None:
    """按篇试看: 放行但告诉业务层只能展示前 300 字"""
    explanation: list = []
    rules = [make_rule(GrantMode.ACCESS, trial_policy={'mode': 'excerpt', 'chars': 300})]

    decision = _run(make_ctx(), rules, explanation, empty_snapshot)

    assert decision is not None
    assert decision.allowed
    assert decision.trial_mode == TrialMode.EXCERPT
    assert decision.trial_excerpt_chars == 300


def test_daily_count_trial_allows_within_limit(empty_snapshot: FakeSnapshot, monkeypatch) -> None:
    """按日体验: 当日第 3 次仍在额度内"""
    explanation: list = []
    rules = [make_rule(GrantMode.ACCESS, trial_policy={'mode': 'daily_count', 'limit': 3})]

    async def fake_incr(_key):
        return 3

    async def fake_expire(_key, _ttl):
        return True

    monkeypatch.setattr('backend.app.access.engine.evaluators.trial_policy.redis_client.incr', fake_incr)
    monkeypatch.setattr('backend.app.access.engine.evaluators.trial_policy.redis_client.expire', fake_expire)

    decision = _run(make_ctx(), rules, explanation, empty_snapshot)

    assert decision is not None
    assert decision.allowed
    assert decision.trial_mode == TrialMode.DAILY_COUNT


def test_daily_count_trial_denies_beyond_limit(empty_snapshot: FakeSnapshot, monkeypatch) -> None:
    """按日体验: 超出当日额度后拒绝"""
    explanation: list = []
    rules = [make_rule(GrantMode.ACCESS, trial_policy={'mode': 'daily_count', 'limit': 3})]

    async def fake_incr(_key):
        return 4

    monkeypatch.setattr('backend.app.access.engine.evaluators.trial_policy.redis_client.incr', fake_incr)

    decision = _run(make_ctx(), rules, explanation, empty_snapshot)

    assert decision is not None
    assert not decision.allowed
    assert decision.reason_code == ReasonCode.TRIAL_EXHAUSTED


def test_daily_count_trial_precheck_does_not_increment(empty_snapshot: FakeSnapshot, monkeypatch) -> None:
    """预检模式不得消耗试看次数"""
    explanation: list = []
    rules = [make_rule(GrantMode.ACCESS, trial_policy={'mode': 'daily_count', 'limit': 3})]
    calls: list[str] = []

    async def fake_incr(_key):
        calls.append('incr')
        return 1

    async def fake_get(_key):
        return '1'

    monkeypatch.setattr('backend.app.access.engine.evaluators.trial_policy.redis_client.incr', fake_incr)
    monkeypatch.setattr('backend.app.access.engine.evaluators.trial_policy.redis_client.get', fake_get)

    decision = _run(make_ctx(consume_trial=False), rules, explanation, empty_snapshot)

    assert decision is not None
    assert decision.allowed
    assert calls == []


def test_daily_count_trial_degrades_open_when_redis_down(empty_snapshot: FakeSnapshot, monkeypatch) -> None:
    """计数器故障时降级放行, 不把付费引导变成硬故障"""
    explanation: list = []
    rules = [make_rule(GrantMode.ACCESS, trial_policy={'mode': 'daily_count', 'limit': 3})]

    async def broken_incr(_key):
        raise RuntimeError('redis down')

    monkeypatch.setattr('backend.app.access.engine.evaluators.trial_policy.redis_client.incr', broken_incr)

    decision = _run(make_ctx(), rules, explanation, empty_snapshot)

    assert decision is not None
    assert decision.allowed
    assert decision.reason_code == ReasonCode.TRIAL_POLICY
