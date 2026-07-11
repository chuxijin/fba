#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import importlib

from datetime import datetime


my_service_module = importlib.import_module('backend.app.access.service.my_service')
crud_ledger_module = importlib.import_module('backend.app.access.crud.crud_ledger')
ledger_module = importlib.import_module('backend.app.access.engine.ledger')


def test_my_access_service_load_quota_balances_uses_scope_key(monkeypatch) -> None:
    """权益汇总应按资源档案解析的 scope_key 读取配额余额"""
    captured: dict[str, object] = {}

    async def fake_get_latest_entries(_db, *, user_id, entitlement_cycle_keys, scope_key):
        captured['user_id'] = user_id
        captured['entitlement_cycle_keys'] = dict(entitlement_cycle_keys)
        captured['scope_key'] = scope_key
        return {'render_book.export.quota': 19}

    async def fake_get_quota_cycle_types_from_rules(*_args, **_kwargs) -> dict[str, str]:
        return {}

    async def fake_get_quota_scope_keys_from_rules(*_args, **_kwargs) -> dict[str, str]:
        return {'render_book.export.quota': 'render_book'}

    monkeypatch.setattr(
        crud_ledger_module.quota_ledger_dao,
        'get_latest_entries',
        fake_get_latest_entries,
    )
    monkeypatch.setattr(
        my_service_module.MyAccessService,
        '_get_quota_cycle_types_from_items',
        staticmethod(lambda *_args, **_kwargs: {'render_book.export.quota': 'daily'}),
    )
    monkeypatch.setattr(
        my_service_module.MyAccessService,
        '_get_quota_cycle_types_from_rules',
        fake_get_quota_cycle_types_from_rules,
    )
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
            pack_items=[],
            quota_codes=['render_book.export.quota'],
        )
    )

    assert balances['render_book.export.quota'] == 19
    assert captured['user_id'] == 20
    assert captured['scope_key'] == 'render_book'
    assert captured['entitlement_cycle_keys'] == {'render_book.export.quota': '2026-07-07'}


def test_ledger_append_invalidates_my_summary_cache(monkeypatch) -> None:
    """账本写入后应失效我的权益汇总缓存"""

    class FakeDB:
        def add(self, _entry) -> None:
            return None

        async def flush(self) -> None:
            return None

    captured: dict[str, object] = {}

    async def fake_invalidate(user_id: int) -> None:
        captured['user_id'] = user_id

    monkeypatch.setattr(my_service_module.my_summary_cache, 'invalidate', fake_invalidate)

    asyncio.run(
        ledger_module.ledger_service._append(
            FakeDB(),
            user_id=20,
            entitlement_code='render_book.export.quota',
            operation='credit',
            amount=1,
            cycle_type='daily',
            cycle_key='2026-07-07',
            scope_key='render_book',
            source='admin',
            source_ref='manual.test',
            idempotency_key='manual.test',
            reason='test append',
            current_balance=0,
        )
    )

    assert captured['user_id'] == 20
