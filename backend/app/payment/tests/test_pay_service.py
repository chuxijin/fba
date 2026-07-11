#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import importlib

from types import SimpleNamespace


pay_service_module = importlib.import_module('backend.app.payment.service.pay_service')


def test_close_payment_can_close_pending_pay_order_without_transaction(monkeypatch) -> None:
    """没有 pending 交易记录时，仍可关闭挂起的业务订单"""
    captured: dict[str, object] = {}

    order = SimpleNamespace(id=11, status='pending', extra_data={'env': 0})

    async def fake_get_order(_db, _order_no):
        return order

    async def fake_get_transaction(_db, _order_no, status=None):
        return None

    async def fake_update_order(_db, order_id, data):
        captured['order_id'] = order_id
        captured['data'] = dict(data)
        return 1

    monkeypatch.setattr(pay_service_module.pay_order_dao, 'get_by_order_no', fake_get_order)
    monkeypatch.setattr(pay_service_module.pay_transaction_dao, 'get_by_order_no', fake_get_transaction)
    monkeypatch.setattr(pay_service_module.pay_order_dao, 'update_model', fake_update_order)
    monkeypatch.setattr(pay_service_module.PayService, '_notifier', None)

    closed = asyncio.run(pay_service_module.PayService.close_payment(db=None, order_no='PO202607070001'))

    assert closed is True
    assert captured['order_id'] == 11
    assert captured['data']['status'] == 'closed'
    assert captured['data']['closed_time'] is not None


def test_close_timeout_pending_orders_returns_summary(monkeypatch) -> None:
    """超时关单任务应区分关闭、跳过和失败结果"""

    class FakeDB:
        def __init__(self) -> None:
            self.commit_count = 0
            self.rollback_count = 0

        async def commit(self) -> None:
            self.commit_count += 1

        async def rollback(self) -> None:
            self.rollback_count += 1

    async def fake_get_timeout_pending_orders(_db, *, created_before, limit):
        assert created_before is not None
        assert limit == 50
        return [
            SimpleNamespace(order_no='PO-CLOSE'),
            SimpleNamespace(order_no='PO-SKIP'),
            SimpleNamespace(order_no='PO-FAIL'),
        ]

    async def fake_close_payment(*, db, order_no):
        if order_no == 'PO-CLOSE':
            return True
        if order_no == 'PO-SKIP':
            return False
        raise RuntimeError('boom')

    monkeypatch.setattr(pay_service_module.settings, 'PAYMENT_PENDING_ORDER_TIMEOUT_MINUTES', 30)
    monkeypatch.setattr(
        pay_service_module.pay_order_dao,
        'get_timeout_pending_orders',
        fake_get_timeout_pending_orders,
    )
    monkeypatch.setattr(pay_service_module.PayService, 'close_payment', staticmethod(fake_close_payment))

    db = FakeDB()
    summary = asyncio.run(
        pay_service_module.PayService.close_timeout_pending_orders(
            db=db,
            limit=50,
        )
    )

    assert summary['timeout_minutes'] == 30
    assert summary['scanned_count'] == 3
    assert summary['closed_count'] == 1
    assert summary['skipped_count'] == 1
    assert summary['failed_count'] == 1
    assert summary['closed_order_nos'] == ['PO-CLOSE']
    assert summary['skipped_order_nos'] == ['PO-SKIP']
    assert summary['failed_order_nos'] == ['PO-FAIL']
    assert db.commit_count == 1
    assert db.rollback_count == 1
