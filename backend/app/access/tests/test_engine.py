#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from types import SimpleNamespace

import pytest

from backend.app.access.constants import DecisionKind, GrantMode, ReasonCode
from backend.app.access.engine.decide import AccessDecisionEngine
from backend.app.access.engine.evaluators import DEFAULT_EVALUATORS

from backend.app.access.tests.conftest import FakeSnapshot, make_ctx, make_rule


class _StubSession:
    """伪 db session, 仅捕获被 add 的对象用于断言"""

    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        """收集 INSERT 对象"""
        self.added.append(obj)


def _patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rules: list,
    snapshot: FakeSnapshot,
) -> None:
    """
    替换决策引擎的 resolver / snapshot, 使其返回测试数据

    :param monkeypatch: pytest monkeypatch
    :param rules: 规则列表
    :param snapshot: 用户快照
    :return:
    """

    async def fake_resolve(*_args, **_kwargs):
        return rules

    async def fake_load(*_args, **_kwargs):
        return snapshot

    monkeypatch.setattr(
        'backend.app.access.engine.decide.rule_resolver.resolve', fake_resolve
    )
    monkeypatch.setattr(
        'backend.app.access.engine.decide.snapshot_service.load', fake_load
    )


@pytest.mark.asyncio
async def test_engine_grants_when_no_rules(monkeypatch) -> None:
    """资源无任何规则, 视为公开资源放行"""
    _patch_pipeline(monkeypatch, rules=[], snapshot=FakeSnapshot())

    engine = AccessDecisionEngine()
    db = _StubSession()
    decision = await engine.decide(db, make_ctx())

    assert decision.allowed
    assert decision.decision == DecisionKind.ALLOW
    assert decision.reason_code == ReasonCode.FREE_RESOURCE
    assert db.added == []


@pytest.mark.asyncio
async def test_engine_denies_when_no_matching_grant(monkeypatch) -> None:
    """有 access 规则但用户无任何权益, 拒绝并写日志"""
    _patch_pipeline(
        monkeypatch,
        rules=[make_rule(GrantMode.ACCESS, entitlement_code='qbank.kaoyan.access')],
        snapshot=FakeSnapshot(),
    )

    engine = AccessDecisionEngine()
    db = _StubSession()
    decision = await engine.decide(db, make_ctx())

    assert not decision.allowed
    assert decision.decision == DecisionKind.DENY
    assert decision.reason_code == ReasonCode.NO_MATCHING_GRANT
    assert len(db.added) == 1


@pytest.mark.asyncio
async def test_engine_grants_via_subscription_and_skips_trial(monkeypatch) -> None:
    """订阅命中后责任链短路, 试看额度不被消耗"""

    consume_calls: list = []

    async def spy_try_consume(*args, **kwargs):
        consume_calls.append((args, kwargs))
        return SimpleNamespace(id=999, balance_after=0)

    monkeypatch.setattr(
        'backend.app.access.engine.evaluators.quota_trial.ledger_service.try_consume',
        spy_try_consume,
    )

    _patch_pipeline(
        monkeypatch,
        rules=[
            make_rule(GrantMode.ACCESS, entitlement_code='qbank.kaoyan.access'),
            make_rule(GrantMode.TRIAL, entitlement_code='content.kaoyan.trial', rule_id=2),
        ],
        snapshot=FakeSnapshot(entitlements={'qbank.kaoyan.access': 1}),
    )

    engine = AccessDecisionEngine()
    db = _StubSession()
    decision = await engine.decide(db, make_ctx())

    assert decision.allowed
    assert decision.reason_code == ReasonCode.SUBSCRIPTION_ACCESS
    assert consume_calls == [], '订阅命中后不应再调用试看扣减'
    assert db.added == [], '允许路径不应写决策日志'


@pytest.mark.asyncio
async def test_engine_falls_through_to_quota_trial(monkeypatch) -> None:
    """订阅未命中 + 无直接授予 → 走试看, 扣减成功放行"""

    async def fake_try_consume(*_args, **_kwargs):
        return SimpleNamespace(id=2002, balance_after=2)

    monkeypatch.setattr(
        'backend.app.access.engine.evaluators.quota_trial.ledger_service.try_consume',
        fake_try_consume,
    )

    _patch_pipeline(
        monkeypatch,
        rules=[
            make_rule(GrantMode.ACCESS, entitlement_code='content.kaoyan.view'),
            make_rule(GrantMode.TRIAL, entitlement_code='content.kaoyan.trial', rule_id=2),
        ],
        snapshot=FakeSnapshot(),
    )

    engine = AccessDecisionEngine()
    db = _StubSession()
    decision = await engine.decide(db, make_ctx())

    assert decision.allowed
    assert decision.reason_code == ReasonCode.QUOTA_TRIAL
    assert decision.consumed_ledger_id == 2002


@pytest.mark.asyncio
async def test_engine_records_explanation_path(monkeypatch) -> None:
    """决策对象 explanation 包含完整责任链路径"""
    _patch_pipeline(
        monkeypatch,
        rules=[make_rule(GrantMode.ACCESS, entitlement_code='qbank.kaoyan.access')],
        snapshot=FakeSnapshot(entitlements={'qbank.kaoyan.access': 1}),
    )

    engine = AccessDecisionEngine()
    decision = await engine.decide(_StubSession(), make_ctx())

    assert len(decision.explanation) >= 3
    evaluators_seen = [node.evaluator for node in decision.explanation]
    assert 'FreePassEvaluator' in evaluators_seen
    assert 'OwnershipEvaluator' in evaluators_seen
    assert 'SubscriptionAccessEvaluator' in evaluators_seen


@pytest.mark.asyncio
async def test_engine_writes_log_only_on_deny(monkeypatch) -> None:
    """允许路径不写日志, 拒绝路径写一条"""
    _patch_pipeline(
        monkeypatch,
        rules=[make_rule(GrantMode.ACCESS, entitlement_code='qbank.kaoyan.access')],
        snapshot=FakeSnapshot(),
    )

    engine = AccessDecisionEngine()
    db = _StubSession()
    await engine.decide(db, make_ctx(user_id=42))

    assert len(db.added) == 1
    log = db.added[0]
    assert log.user_id == 42
    assert log.decision == DecisionKind.DENY
    assert log.reason_code == ReasonCode.NO_MATCHING_GRANT


@pytest.mark.asyncio
async def test_engine_handles_kaoyan_user_accessing_kaogong(
    monkeypatch, vip_kaoyan_snapshot
) -> None:
    """考研 VIP 用户访问考公付费题库, 应当被拒绝(多领域并存核心场景)"""
    _patch_pipeline(
        monkeypatch,
        rules=[make_rule(GrantMode.ACCESS, entitlement_code='qbank.kaogong.access')],
        snapshot=vip_kaoyan_snapshot,
    )

    engine = AccessDecisionEngine()
    decision = await engine.decide(_StubSession(), make_ctx())

    assert not decision.allowed
    assert decision.reason_code == ReasonCode.NO_MATCHING_GRANT


@pytest.mark.asyncio
async def test_engine_grants_all_in_one_user_for_any_domain(
    monkeypatch, all_in_one_svip_snapshot
) -> None:
    """全家桶 SVIP 用户访问任意领域付费题库, 全部放行"""
    for code in ['qbank.kaoyan.access', 'qbank.kaogong.access', 'qbank.cet.access']:
        _patch_pipeline(
            monkeypatch,
            rules=[make_rule(GrantMode.ACCESS, entitlement_code=code)],
            snapshot=all_in_one_svip_snapshot,
        )
        decision = await AccessDecisionEngine().decide(_StubSession(), make_ctx())
        assert decision.allowed
        assert decision.matched_grant == code


@pytest.mark.asyncio
async def test_default_evaluators_chain_order() -> None:
    """默认评估器责任链顺序: FreePass → Ownership → Subscription → DirectGrant → QuotaTrial"""
    names = [e.name for e in DEFAULT_EVALUATORS]
    assert names == [
        'FreePassEvaluator',
        'OwnershipEvaluator',
        'SubscriptionAccessEvaluator',
        'DirectGrantEvaluator',
        'QuotaTrialEvaluator',
    ]
