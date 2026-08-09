#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from types import SimpleNamespace

import pytest

from backend.app.access.constants import GrantMode, ReasonCode
from backend.app.access.engine.evaluators.direct_grant import DirectGrantEvaluator
from backend.app.access.engine.evaluators.free_pass import FreePassEvaluator
from backend.app.access.engine.evaluators.metered import MeteredEvaluator
from backend.app.access.engine.evaluators.subscription_access import SubscriptionAccessEvaluator

from backend.app.access.tests.conftest import FakeSnapshot, make_ctx, make_rule


@pytest.mark.asyncio
async def test_free_pass_grants_when_rule_present(empty_snapshot: FakeSnapshot) -> None:
    """限时免费规则命中, 即使用户无任何权益也放行"""
    evaluator = FreePassEvaluator()
    rules = [make_rule(GrantMode.FREE_PASS, entitlement_code='qbank.holiday_pass')]
    explanation: list = []

    decision = await evaluator.evaluate(None, make_ctx(), rules, empty_snapshot, explanation)

    assert decision is not None
    assert decision.allowed
    assert decision.reason_code == ReasonCode.FREE_PASS
    assert decision.matched_grant == 'qbank.holiday_pass'
    assert any(node.outcome == 'allow' for node in decision.explanation)


@pytest.mark.asyncio
async def test_free_pass_passes_when_no_free_pass_rule(empty_snapshot: FakeSnapshot) -> None:
    """无 free_pass 规则, 评估器让出给下一环"""
    evaluator = FreePassEvaluator()
    rules = [make_rule(GrantMode.ACCESS), make_rule(GrantMode.METERED, rule_id=2)]
    explanation: list = []

    decision = await evaluator.evaluate(None, make_ctx(), rules, empty_snapshot, explanation)

    assert decision is None
    assert len(explanation) == 1
    assert explanation[0].outcome == 'pass'


@pytest.mark.asyncio
async def test_subscription_access_grants_for_holder(vip_kaoyan_snapshot: FakeSnapshot) -> None:
    """用户通过订阅持有目标权益, 放行"""
    evaluator = SubscriptionAccessEvaluator()
    rules = [make_rule(GrantMode.ACCESS, entitlement_code='qbank.kaoyan.access')]
    explanation: list = []

    decision = await evaluator.evaluate(None, make_ctx(), rules, vip_kaoyan_snapshot, explanation)

    assert decision is not None
    assert decision.allowed
    assert decision.reason_code == ReasonCode.SUBSCRIPTION_ACCESS
    assert decision.matched_grant == 'qbank.kaoyan.access'


@pytest.mark.asyncio
async def test_subscription_access_misses_for_other_domain(vip_kaoyan_snapshot: FakeSnapshot) -> None:
    """考研 VIP 用户访问考公付费题库, 订阅评估器让出"""
    evaluator = SubscriptionAccessEvaluator()
    rules = [make_rule(GrantMode.ACCESS, entitlement_code='qbank.kaogong.access')]
    explanation: list = []

    decision = await evaluator.evaluate(None, make_ctx(), rules, vip_kaoyan_snapshot, explanation)

    assert decision is None


@pytest.mark.asyncio
async def test_subscription_access_ignores_non_access_rules(vip_kaoyan_snapshot: FakeSnapshot) -> None:
    """订阅评估器只看 grant_mode=access 规则, 跳过 trial / free_pass"""
    evaluator = SubscriptionAccessEvaluator()
    rules = [
        make_rule(GrantMode.METERED, entitlement_code='qbank.kaoyan.access'),
        make_rule(GrantMode.FREE_PASS, entitlement_code='qbank.kaoyan.access', rule_id=2),
    ]
    explanation: list = []

    decision = await evaluator.evaluate(None, make_ctx(), rules, vip_kaoyan_snapshot, explanation)

    assert decision is None


@pytest.mark.asyncio
async def test_direct_grant_grants_when_user_has_grant(direct_grant_snapshot: FakeSnapshot) -> None:
    """用户拥有匹配的直接授予, 放行"""
    evaluator = DirectGrantEvaluator()
    rules = [make_rule(GrantMode.ACCESS, entitlement_code='qbank.kaoyan.access')]
    explanation: list = []

    decision = await evaluator.evaluate(None, make_ctx(), rules, direct_grant_snapshot, explanation)

    assert decision is not None
    assert decision.allowed
    assert decision.reason_code == ReasonCode.DIRECT_GRANT


@pytest.mark.asyncio
async def test_direct_grant_passes_when_user_lacks_grant(empty_snapshot: FakeSnapshot) -> None:
    """用户无直接授予, 评估器让出"""
    evaluator = DirectGrantEvaluator()
    rules = [make_rule(GrantMode.ACCESS, entitlement_code='qbank.kaoyan.access')]
    explanation: list = []

    decision = await evaluator.evaluate(None, make_ctx(), rules, empty_snapshot, explanation)

    assert decision is None


@pytest.mark.asyncio
async def test_metered_consumes_and_grants(empty_snapshot: FakeSnapshot, monkeypatch) -> None:
    """有额度包余额, 扣减成功放行"""
    fake_entry = SimpleNamespace(id=1001, balance_after=2)

    async def fake_try_consume(*_args, **_kwargs):
        return fake_entry

    monkeypatch.setattr(
        'backend.app.access.engine.evaluators.metered.ledger_service.try_consume',
        fake_try_consume,
    )

    evaluator = MeteredEvaluator()
    rules = [make_rule(GrantMode.METERED, entitlement_code='content.kaoyan.quota')]
    explanation: list = []

    decision = await evaluator.evaluate(None, make_ctx(), rules, empty_snapshot, explanation)

    assert decision is not None
    assert decision.allowed
    assert decision.reason_code == ReasonCode.METERED_CONSUMED
    assert decision.consumed_ledger_id == 1001


@pytest.mark.asyncio
async def test_metered_consumes_with_scope_and_source_ref(empty_snapshot: FakeSnapshot, monkeypatch) -> None:
    """扣减应带上业务范围与来源引用，保证幂等隔离"""
    captured: dict[str, object] = {}
    fake_entry = SimpleNamespace(id=1002, balance_after=1)

    async def fake_try_consume(*_args, **kwargs):
        captured.update(kwargs)
        return fake_entry

    monkeypatch.setattr(
        'backend.app.access.engine.evaluators.metered.ledger_service.try_consume',
        fake_try_consume,
    )

    evaluator = MeteredEvaluator()
    rules = [make_rule(GrantMode.METERED, entitlement_code='content.render_book.quota')]
    explanation: list = []

    decision = await evaluator.evaluate(
        None,
        make_ctx(scope_key='render_book', source_ref='render_job:job_001'),
        rules,
        empty_snapshot,
        explanation,
    )

    assert decision is not None
    assert decision.allowed
    assert captured['scope_key'] == 'render_book'
    assert captured['source_ref'] == 'render_job:job_001'
    assert captured['idempotency_key'] == 'metered:42:content.render_book.quota:render_book:render_job:job_001'


@pytest.mark.asyncio
async def test_metered_precheck_reads_balance_by_scope(empty_snapshot: FakeSnapshot, monkeypatch) -> None:
    """预检应按 scope_key 读取余额，避免串用其他业务配额"""
    captured: dict[str, object] = {}

    async def fake_get_balance(*_args, **kwargs):
        captured.update(kwargs)
        return 3

    monkeypatch.setattr(
        'backend.app.access.engine.evaluators.metered.ledger_service.get_balance',
        fake_get_balance,
    )

    evaluator = MeteredEvaluator()
    rules = [make_rule(GrantMode.METERED, entitlement_code='content.render_book.quota')]
    explanation: list = []

    decision = await evaluator.evaluate(
        None,
        make_ctx(consume_trial=False, scope_key='render_book'),
        rules,
        empty_snapshot,
        explanation,
    )

    assert decision is not None
    assert decision.allowed
    assert captured['scope_key'] == 'render_book'
    assert captured['entitlement_code'] == 'content.render_book.quota'


@pytest.mark.asyncio
async def test_metered_denies_when_grant_drained(empty_snapshot: FakeSnapshot, monkeypatch) -> None:
    """曾经有额度包但已耗尽, 拒绝并引导升级"""

    async def fake_try_consume(*_args, **_kwargs):
        return None

    async def fake_exists_any(*_args, **_kwargs):
        return True

    monkeypatch.setattr(
        'backend.app.access.engine.evaluators.metered.ledger_service.try_consume',
        fake_try_consume,
    )
    monkeypatch.setattr(
        'backend.app.access.engine.evaluators.metered.quota_grant_dao.exists_any',
        fake_exists_any,
    )

    evaluator = MeteredEvaluator()
    rules = [make_rule(GrantMode.METERED, entitlement_code='content.kaoyan.quota')]
    explanation: list = []

    decision = await evaluator.evaluate(None, make_ctx(), rules, empty_snapshot, explanation)

    assert decision is not None
    assert not decision.allowed
    assert decision.reason_code == ReasonCode.QUOTA_EXHAUSTED


@pytest.mark.asyncio
async def test_metered_yields_to_trial_when_never_granted(empty_snapshot: FakeSnapshot, monkeypatch) -> None:
    """从未持有额度包的用户应让位给试看策略, 而不是被判为配额耗尽"""

    async def fake_try_consume(*_args, **_kwargs):
        return None

    async def fake_exists_any(*_args, **_kwargs):
        return False

    monkeypatch.setattr(
        'backend.app.access.engine.evaluators.metered.ledger_service.try_consume',
        fake_try_consume,
    )
    monkeypatch.setattr(
        'backend.app.access.engine.evaluators.metered.quota_grant_dao.exists_any',
        fake_exists_any,
    )

    evaluator = MeteredEvaluator()
    rules = [make_rule(GrantMode.METERED, entitlement_code='content.kaoyan.quota')]
    explanation: list = []

    decision = await evaluator.evaluate(None, make_ctx(), rules, empty_snapshot, explanation)

    assert decision is None
    assert explanation[-1].reason == '用户从未持有该计量配额, 让位给试看策略'


@pytest.mark.asyncio
async def test_metered_passes_when_no_metered_rule(empty_snapshot: FakeSnapshot) -> None:
    """资源无 metered 规则, 评估器让出"""
    evaluator = MeteredEvaluator()
    rules = [make_rule(GrantMode.ACCESS)]
    explanation: list = []

    decision = await evaluator.evaluate(None, make_ctx(), rules, empty_snapshot, explanation)

    assert decision is None
