#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import importlib

from types import SimpleNamespace

import pytest

from backend.app.access.constants import ReasonCode
from backend.app.access.schema.engine import Decision
from backend.app.access.service.resource_access_service import resource_access_service
from backend.app.access.service.resource_profile_registry import AccessProfile
from backend.common.exception import errors

resource_access_service_module = importlib.import_module('backend.app.access.service.resource_access_service')


def test_resource_access_service_ensure_uses_registered_profile(monkeypatch) -> None:
    """预检应按注册档案构造 AccessContext"""
    profile = AccessProfile(
        code='test.resource.ensure',
        resource_type='test_resource',
        resource_id=7,
        action='export',
        scope_key='test_scope',
    )
    resource_access_service.register_profile(profile)

    captured: dict[str, object] = {}

    async def fake_decide(_db, ctx):
        captured['ctx'] = ctx
        return Decision.allow(reason_code=ReasonCode.METERED_CONSUMED)

    monkeypatch.setattr(resource_access_service_module.access_decision_engine, 'decide', fake_decide)

    decision = asyncio.run(
        resource_access_service.ensure(
            None,
            profile_code=profile.code,
            user_id=9,
        )
    )

    assert decision.allowed
    ctx = captured['ctx']
    assert ctx.resource_type == 'test_resource'
    assert ctx.resource_id == 7
    assert ctx.action == 'export'
    assert ctx.scope_key == 'test_scope'
    assert not ctx.consume_trial


def test_resource_access_service_ensure_raises_profile_message(monkeypatch) -> None:
    """预检拒绝时应返回档案级提示"""
    profile = AccessProfile(
        code='test.resource.raise',
        resource_type='test_resource',
        resource_id=8,
        deny_messages={ReasonCode.QUOTA_EXHAUSTED: '测试配额已耗尽'},
        default_deny_message='默认拒绝',
    )
    resource_access_service.register_profile(profile)

    async def fake_decide(*_args, **_kwargs):
        return Decision.deny(reason_code=ReasonCode.QUOTA_EXHAUSTED)

    monkeypatch.setattr(resource_access_service_module.access_decision_engine, 'decide', fake_decide)

    with pytest.raises(errors.ForbiddenError, match='测试配额已耗尽'):
        asyncio.run(
            resource_access_service.ensure(
                None,
                profile_code=profile.code,
                user_id=9,
            )
        )


def test_resource_access_service_consume_can_return_deny_without_raise(monkeypatch) -> None:
    """业务可选择在扣减失败时只拿决策结果，不抛异常"""
    profile = AccessProfile(
        code='test.resource.consume',
        resource_type='test_resource',
        resource_id=9,
    )
    resource_access_service.register_profile(profile)

    captured: dict[str, object] = {}

    async def fake_decide(_db, ctx):
        captured['ctx'] = ctx
        return Decision.deny(reason_code=ReasonCode.NO_MATCHING_GRANT)

    monkeypatch.setattr(resource_access_service_module.access_decision_engine, 'decide', fake_decide)

    decision = asyncio.run(
        resource_access_service.consume(
            None,
            profile_code=profile.code,
            user_id=9,
            source_ref='task:1',
            raise_on_deny=False,
        )
    )

    assert not decision.allowed
    ctx = captured['ctx']
    assert ctx.consume_trial
    assert ctx.source_ref == 'task:1'


def test_resource_access_service_refund_uses_ledger_entry(monkeypatch) -> None:
    """回滚应按原扣减流水精确回补额度包"""
    profile = AccessProfile(
        code='test.resource.refund',
        resource_type='test_resource',
        resource_id=10,
        refund_reason='test refund reason',
    )
    resource_access_service.register_profile(profile)

    async def fake_select_model(*_args, **_kwargs):
        return SimpleNamespace(
            id=123,
            user_id=9,
            entitlement_code='test.entitlement.quota',
            amount=1,
            cycle_type='daily',
            cycle_key='2026-07-07',
            scope_key='test_scope',
        )

    captured: dict[str, object] = {}

    async def fake_refund_consumption(*_args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(resource_access_service_module.quota_ledger_dao, 'select_model', fake_select_model)
    monkeypatch.setattr(
        resource_access_service_module.ledger_service,
        'refund_consumption',
        fake_refund_consumption,
    )

    decision = Decision.allow(reason_code=ReasonCode.METERED_CONSUMED, consumed_ledger_id=123)
    asyncio.run(
        resource_access_service.refund(
            None,
            profile_code=profile.code,
            user_id=9,
            decision=decision,
            source_ref='biz:refund:1',
        )
    )

    assert captured['ledger_id'] == 123
    assert captured['source_ref'] == 'biz:refund:1'
    assert captured['idempotency_key'] == 'refund:123'
    assert captured['reason'] == 'test refund reason'


def test_resource_access_service_refund_skips_other_users_ledger(monkeypatch) -> None:
    """流水不属于当前用户时不得回补, 防止跨账号退款"""
    profile = AccessProfile(
        code='test.resource.refund.owner',
        resource_type='test_resource',
        resource_id=11,
        refund_reason='test refund reason',
    )
    resource_access_service.register_profile(profile)

    async def fake_select_model(*_args, **_kwargs):
        return SimpleNamespace(
            id=456,
            user_id=999,
            entitlement_code='test.entitlement.quota',
            amount=1,
            cycle_type='daily',
            cycle_key='2026-07-07',
            scope_key='test_scope',
        )

    called: dict[str, object] = {}

    async def fake_refund_consumption(*_args, **kwargs):
        called.update(kwargs)

    monkeypatch.setattr(resource_access_service_module.quota_ledger_dao, 'select_model', fake_select_model)
    monkeypatch.setattr(
        resource_access_service_module.ledger_service,
        'refund_consumption',
        fake_refund_consumption,
    )

    decision = Decision.allow(reason_code=ReasonCode.METERED_CONSUMED, consumed_ledger_id=456)
    asyncio.run(
        resource_access_service.refund(
            None,
            profile_code=profile.code,
            user_id=9,
            decision=decision,
        )
    )

    assert called == {}


def test_resource_access_service_refund_releases_daily_trial(monkeypatch) -> None:
    """带幂等标识的按日体验失败后应回退一次计数。"""
    profile = AccessProfile(
        code='test.resource.trial-refund',
        resource_type='test_resource',
        resource_id=12,
    )
    resource_access_service.register_profile(profile)
    captured: dict[str, object] = {}

    async def fake_refund_once(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(
        resource_access_service_module.trial_counter_service,
        'refund_once',
        fake_refund_once,
    )

    decision = Decision.allow(
        reason_code=ReasonCode.TRIAL_POLICY,
        trial_mode='daily_count',
        trial_counter_key='access:trial:counter',
        trial_idempotency_key='access:trial:source',
    )
    asyncio.run(
        resource_access_service.refund(
            None,
            profile_code=profile.code,
            user_id=9,
            decision=decision,
        )
    )

    assert captured == {
        'counter_key': 'access:trial:counter',
        'idempotency_key': 'access:trial:source',
    }
