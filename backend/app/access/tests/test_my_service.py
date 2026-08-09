#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import importlib

from datetime import datetime


my_service_module = importlib.import_module('backend.app.access.service.my_service')
crud_quota_grant_module = importlib.import_module('backend.app.access.crud.crud_quota_grant')
ledger_module = importlib.import_module('backend.app.access.engine.ledger')


def test_my_access_service_load_quota_balances_uses_scope_key(monkeypatch) -> None:
    """权益汇总应按资源档案解析的 scope_key 聚合额度包余额"""
    captured: dict[str, object] = {}

    async def fake_get_balances(_db, *, user_id, entitlement_codes, scope_key, ts):
        captured['user_id'] = user_id
        captured['entitlement_codes'] = list(entitlement_codes)
        captured['scope_key'] = scope_key
        captured['ts'] = ts
        return {'render_book.export.quota': 19}

    async def fake_get_quota_scope_keys_from_rules(*_args, **_kwargs) -> dict[str, str]:
        return {'render_book.export.quota': 'render_book'}

    monkeypatch.setattr(
        crud_quota_grant_module.quota_grant_dao,
        'get_balances',
        fake_get_balances,
    )
    monkeypatch.setattr(
        my_service_module.MyAccessService,
        '_get_quota_scope_keys_from_rules',
        fake_get_quota_scope_keys_from_rules,
    )

    now = datetime(2026, 7, 7, 21, 30, 0)
    balances = asyncio.run(
        my_service_module.MyAccessService._load_quota_balances(
            None,
            user_id=20,
            now=now,
            pack_items=[],
            quota_codes=['render_book.export.quota'],
        )
    )

    assert balances['render_book.export.quota'] == 19
    assert captured['user_id'] == 20
    assert captured['scope_key'] == 'render_book'
    assert captured['entitlement_codes'] == ['render_book.export.quota']
    assert captured['ts'] == now


def test_load_quota_balances_falls_back_to_pack_limit(monkeypatch) -> None:
    """尚未生成额度包时应回退展示权益包配置的名义额度"""

    async def fake_get_balances(*_args, **_kwargs) -> dict[str, int]:
        return {}

    async def fake_get_quota_scope_keys_from_rules(*_args, **_kwargs) -> dict[str, str]:
        return {}

    monkeypatch.setattr(crud_quota_grant_module.quota_grant_dao, 'get_balances', fake_get_balances)
    monkeypatch.setattr(
        my_service_module.MyAccessService,
        '_get_quota_scope_keys_from_rules',
        fake_get_quota_scope_keys_from_rules,
    )

    balances = asyncio.run(
        my_service_module.MyAccessService._load_quota_balances(
            None,
            user_id=20,
            now=datetime(2026, 7, 7, 21, 30, 0),
            pack_items=[{'entitlement_code': 'agent.grade.quota', 'value_int': 30, 'value_meta': {}}],
            quota_codes=['agent.grade.quota'],
        )
    )

    assert balances['agent.grade.quota'] == 30


class _FakeGrant:
    """额度包替身"""

    def __init__(self, grant_id: int, remaining: int) -> None:
        self.id = grant_id
        self.granted_amount = remaining
        self.remaining_amount = remaining


class _FakeDB:
    """只记录写入的会话替身"""

    def __init__(self) -> None:
        self.added: list = []

    def add(self, entry) -> None:
        self.added.append(entry)

    async def flush(self) -> None:
        return None


def test_try_consume_drains_expiring_grant_first(monkeypatch) -> None:
    """扣减应跨包消耗, 先扣即将失效的包, 并失效我的权益汇总缓存"""
    # list_consumable 已按 expires_at 升序返回: 1 号包月底过期, 2 号包永不过期
    grants = [_FakeGrant(1, 2), _FakeGrant(2, 5)]
    captured: dict[str, object] = {}

    async def fake_ensure_cycle_grant(*_args, **_kwargs) -> None:
        return None

    async def fake_get_by_idempotency_key(*_args, **_kwargs):
        return None

    async def fake_list_consumable(*_args, **_kwargs):
        return grants

    async def fake_invalidate(user_id: int) -> None:
        captured['user_id'] = user_id

    monkeypatch.setattr(
        ledger_module.LedgerService,
        '_ensure_cycle_grant',
        staticmethod(fake_ensure_cycle_grant),
    )
    monkeypatch.setattr(
        ledger_module.quota_ledger_dao,
        'get_by_idempotency_key',
        fake_get_by_idempotency_key,
    )
    monkeypatch.setattr(ledger_module.quota_grant_dao, 'list_consumable', fake_list_consumable)
    monkeypatch.setattr(my_service_module.my_summary_cache, 'invalidate', fake_invalidate)

    entry = asyncio.run(
        ledger_module.ledger_service.try_consume(
            _FakeDB(),
            user_id=20,
            entitlement_code='agent.grade.quota',
            amount=3,
            cycle_type='monthly',
            scope_key='global',
            source='metered',
            source_ref='job:1',
            idempotency_key='job:1',
        )
    )

    assert entry is not None
    # 先扣光 1 号包的 2 次, 再从 2 号包扣 1 次
    assert grants[0].remaining_amount == 0
    assert grants[1].remaining_amount == 4
    assert entry.grant_breakdown == [{'grant_id': 1, 'amount': 2}, {'grant_id': 2, 'amount': 1}]
    assert entry.balance_after == 4
    assert captured['user_id'] == 20


def test_try_consume_returns_none_when_total_insufficient(monkeypatch) -> None:
    """所有额度包合计不足时不扣减并返回 None"""
    grants = [_FakeGrant(1, 1)]

    async def fake_ensure_cycle_grant(*_args, **_kwargs) -> None:
        return None

    async def fake_get_by_idempotency_key(*_args, **_kwargs):
        return None

    async def fake_list_consumable(*_args, **_kwargs):
        return grants

    monkeypatch.setattr(
        ledger_module.LedgerService,
        '_ensure_cycle_grant',
        staticmethod(fake_ensure_cycle_grant),
    )
    monkeypatch.setattr(
        ledger_module.quota_ledger_dao,
        'get_by_idempotency_key',
        fake_get_by_idempotency_key,
    )
    monkeypatch.setattr(ledger_module.quota_grant_dao, 'list_consumable', fake_list_consumable)

    entry = asyncio.run(
        ledger_module.ledger_service.try_consume(
            _FakeDB(),
            user_id=20,
            entitlement_code='agent.grade.quota',
            amount=3,
            cycle_type='monthly',
            source='metered',
        )
    )

    assert entry is None
    assert grants[0].remaining_amount == 1
