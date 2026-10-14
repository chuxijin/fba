#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from collections.abc import Callable
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.app.payment.service import pay_service as pay_service_module
from backend.common.exception import errors

ORDER_NO = 'PO20261009001'
TRADE_NO = 'TX20261009001'
AMOUNT = Decimal('19.90')
TOTAL_FEE = 1990


@pytest.fixture
def notifier(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """替换业务通知器，避免真实发放并记录调用。"""
    stub = SimpleNamespace(
        on_payment_success=AsyncMock(),
        on_refund_success=AsyncMock(),
        on_payment_closed=AsyncMock(),
    )
    monkeypatch.setattr(pay_service_module.PayService, '_notifier', stub)
    return stub


def _transaction(status: str = 'pending') -> SimpleNamespace:
    """构造支付记录替身。"""
    return SimpleNamespace(
        id=1,
        order_no=ORDER_NO,
        pay_type='hupijiao',
        amount=AMOUNT,
        status=status,
        trade_no='',
        paid_time=None,
        notify_data=None,
        refund_amount=None,
        refunded_time=None,
    )


def _order(status: str = 'pending', fulfill_status: str = 'pending') -> SimpleNamespace:
    """构造业务订单替身。"""
    return SimpleNamespace(
        id=11,
        order_no=ORDER_NO,
        status=status,
        fulfill_status=fulfill_status,
        trade_no='',
        paid_time=None,
    )


class _StubProvider:
    """直接返回预设归一化结果的渠道替身。"""

    def __init__(self, normalized: dict) -> None:
        self._normalized = normalized

    def decrypt_callback(self, *, headers: dict, body: bytes) -> dict:
        return {'raw': True}

    def normalize_callback_data(self, callback_data: dict, *, event: str = 'payment') -> dict:
        return dict(self._normalized)


def _install(
    monkeypatch: pytest.MonkeyPatch,
    txn: SimpleNamespace | None,
    order: SimpleNamespace,
    provider: _StubProvider,
) -> dict:
    """替换渠道解析与数据访问层，返回更新记录。"""
    updates: dict[str, list] = {'txn': [], 'order': []}

    def apply(target: SimpleNamespace, bucket: str) -> Callable[[Any, Any, dict], int]:
        """生成写库替身，同时把变更同步到替身对象。"""

        def side_effect(_db: Any, _pk: Any, data: dict) -> int:
            updates[bucket].append(dict(data))
            for key, value in data.items():
                setattr(target, key, value)
            return 1

        return side_effect

    monkeypatch.setattr(pay_service_module, 'decrypt_callback', lambda **kwargs: ({'raw': True}, provider))
    monkeypatch.setattr(pay_service_module, 'get_provider', lambda _pay_type: provider)
    monkeypatch.setattr(
        pay_service_module.pay_transaction_dao,
        'get',
        AsyncMock(side_effect=lambda _db, _pk, *, for_update=False: txn),
    )
    monkeypatch.setattr(
        pay_service_module.pay_transaction_dao,
        'get_by_order_no',
        AsyncMock(side_effect=lambda _db, _order_no, status=None, *, for_update=False: txn),
    )
    monkeypatch.setattr(
        pay_service_module.pay_transaction_dao, 'update_model', AsyncMock(side_effect=apply(txn, 'txn'))
    )
    monkeypatch.setattr(
        pay_service_module.pay_order_dao,
        'get_by_order_no',
        AsyncMock(side_effect=lambda _db, _order_no, *, for_update=False: order),
    )
    monkeypatch.setattr(pay_service_module.pay_order_dao, 'update_model', AsyncMock(side_effect=apply(order, 'order')))
    return updates


def _handle() -> None:
    """以虎皮椒渠道触发一次支付回调处理。"""
    asyncio.run(
        pay_service_module.PayService.handle_pay_callback(
            db=None,
            headers={},
            body=b'raw',
            pay_type='hupijiao',
        )
    )


def test_payment_callback_marks_transaction_and_order_paid(
    monkeypatch: pytest.MonkeyPatch, notifier: SimpleNamespace
) -> None:
    """支付成功回调应同时更新支付记录、业务订单并触发发放。"""
    provider = _StubProvider({
        'order_no': ORDER_NO,
        'trade_no': TRADE_NO,
        'trade_state': 'SUCCESS',
        'total_fee': TOTAL_FEE,
    })
    txn, order = _transaction(), _order()
    updates = _install(monkeypatch, txn, order, provider)

    _handle()

    assert txn.status == 'paid'
    assert txn.trade_no == TRADE_NO
    assert order.status == 'paid'
    assert len(updates['txn']) == 1
    assert len(updates['order']) == 1
    notifier.on_payment_success.assert_awaited_once_with(
        db=None, order_no=ORDER_NO, trade_no=TRADE_NO, paid_amount=AMOUNT
    )


def test_payment_callback_is_idempotent_after_fulfillment(
    monkeypatch: pytest.MonkeyPatch, notifier: SimpleNamespace
) -> None:
    """重复回调不得重复发放权益。"""
    provider = _StubProvider({
        'order_no': ORDER_NO,
        'trade_no': TRADE_NO,
        'trade_state': 'SUCCESS',
        'total_fee': TOTAL_FEE,
    })
    txn, order = _transaction(status='paid'), _order(status='paid', fulfill_status='fulfilled')
    updates = _install(monkeypatch, txn, order, provider)

    _handle()

    assert updates['txn'] == []
    assert updates['order'] == []
    notifier.on_payment_success.assert_not_awaited()


def test_payment_callback_requires_retry_when_order_missing(
    monkeypatch: pytest.MonkeyPatch, notifier: SimpleNamespace
) -> None:
    """订单尚未落库时应报错，让渠道重试而不是提前确认收款。"""
    provider = _StubProvider({
        'order_no': ORDER_NO,
        'trade_no': TRADE_NO,
        'trade_state': 'SUCCESS',
        'total_fee': TOTAL_FEE,
    })
    updates = _install(monkeypatch, None, _order(), provider)

    with pytest.raises(errors.NotFoundError):
        _handle()

    assert updates['txn'] == []
    notifier.on_payment_success.assert_not_awaited()


def test_payment_callback_rejects_amount_mismatch(monkeypatch: pytest.MonkeyPatch, notifier: SimpleNamespace) -> None:
    """金额与订单不一致时不得标记支付成功。"""
    provider = _StubProvider({'order_no': ORDER_NO, 'trade_no': TRADE_NO, 'trade_state': 'SUCCESS', 'total_fee': 1})
    txn, order = _transaction(), _order()
    updates = _install(monkeypatch, txn, order, provider)

    with pytest.raises(errors.RequestError):
        _handle()

    assert txn.status == 'pending'
    assert updates['txn'] == []
    notifier.on_payment_success.assert_not_awaited()


def test_payment_callback_ignores_unpaid_state(monkeypatch: pytest.MonkeyPatch, notifier: SimpleNamespace) -> None:
    """未支付状态不产生任何更新。"""
    provider = _StubProvider({
        'order_no': ORDER_NO,
        'trade_no': TRADE_NO,
        'trade_state': 'NOTPAY',
        'total_fee': TOTAL_FEE,
    })
    txn, order = _transaction(), _order()
    updates = _install(monkeypatch, txn, order, provider)

    _handle()

    assert updates['txn'] == []
    assert updates['order'] == []
    notifier.on_payment_success.assert_not_awaited()


def test_payment_callback_ignores_late_payment_after_refund(
    monkeypatch: pytest.MonkeyPatch, notifier: SimpleNamespace
) -> None:
    """退款完成后的延迟支付通知必须被忽略。"""
    provider = _StubProvider({
        'order_no': ORDER_NO,
        'trade_no': TRADE_NO,
        'trade_state': 'SUCCESS',
        'total_fee': TOTAL_FEE,
    })
    txn, order = _transaction(status='refunded'), _order(status='refunded', fulfill_status='revoked')
    updates = _install(monkeypatch, txn, order, provider)

    _handle()

    assert updates['txn'] == []
    assert updates['order'] == []
    notifier.on_payment_success.assert_not_awaited()


def test_refund_callback_marks_refunded(monkeypatch: pytest.MonkeyPatch, notifier: SimpleNamespace) -> None:
    """退款成功回调应更新记录、订单并通知业务撤销。"""
    provider = _StubProvider({
        'order_no': ORDER_NO,
        'trade_no': TRADE_NO,
        'total_fee': TOTAL_FEE,
        'refund_status': 'SUCCESS',
    })
    txn, order = _transaction(status='paid'), _order(status='paid')
    updates = _install(monkeypatch, txn, order, provider)

    _handle()

    assert txn.status == 'refunded'
    assert txn.refund_amount == AMOUNT
    assert order.status == 'refunded'
    assert updates['order'][0]['status'] == 'refunded'
    notifier.on_refund_success.assert_awaited_once_with(db=None, order_no=ORDER_NO)


def test_refund_callback_processing_marks_pending(monkeypatch: pytest.MonkeyPatch, notifier: SimpleNamespace) -> None:
    """退款处理中应进入退款挂起状态。"""
    provider = _StubProvider({
        'order_no': ORDER_NO,
        'trade_no': TRADE_NO,
        'total_fee': TOTAL_FEE,
        'refund_status': 'PROCESSING',
    })
    txn, order = _transaction(status='paid'), _order(status='paid')
    _install(monkeypatch, txn, order, provider)

    _handle()

    assert txn.status == 'refund_pending'
    assert order.status == 'refund_pending'
    notifier.on_refund_success.assert_not_awaited()


def test_refund_callback_failed_restores_paid(monkeypatch: pytest.MonkeyPatch, notifier: SimpleNamespace) -> None:
    """退款失败应回退为已支付状态。"""
    provider = _StubProvider({
        'order_no': ORDER_NO,
        'trade_no': TRADE_NO,
        'total_fee': TOTAL_FEE,
        'refund_status': 'FAILED',
    })
    txn, order = _transaction(status='refund_pending'), _order(status='refund_pending')
    _install(monkeypatch, txn, order, provider)

    _handle()

    assert txn.status == 'paid'
    assert order.status == 'paid'
    notifier.on_refund_success.assert_not_awaited()


def test_late_payment_restores_user_hidden_closed_order(
    monkeypatch: pytest.MonkeyPatch, notifier: SimpleNamespace
) -> None:
    """用户删除已关闭记录后发生迟到付款，恢复记录且不能再次随退款自动隐藏。"""
    provider = _StubProvider({
        'order_no': ORDER_NO,
        'trade_no': TRADE_NO,
        'trade_state': 'SUCCESS',
        'total_fee': TOTAL_FEE,
    })
    txn, order = _transaction(status='closed'), _order(status='closed')
    order.user_hidden_at = 'previous-hidden-time'
    _install(monkeypatch, txn, order, provider)
    _handle()
    assert order.status == 'paid'
    assert order.user_hidden_at is None
    notifier.on_payment_success.assert_awaited_once()


def test_duplicate_refund_does_not_restore_intentionally_hidden_record(
    monkeypatch: pytest.MonkeyPatch, notifier: SimpleNamespace
) -> None:
    """已经退款并删除的记录不能因重复退款通知重新出现。"""
    provider = _StubProvider({
        'order_no': ORDER_NO,
        'trade_no': TRADE_NO,
        'total_fee': TOTAL_FEE,
        'refund_status': 'SUCCESS',
    })
    txn, order = _transaction(status='refunded'), _order(status='refunded', fulfill_status='revoked')
    order.user_hidden_at = 'previous-hidden-time'
    _install(monkeypatch, txn, order, provider)
    _handle()
    assert order.user_hidden_at == 'previous-hidden-time'
    notifier.on_refund_success.assert_not_awaited()
