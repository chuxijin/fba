#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from backend.app.payment.crud.crud_pay_order import pay_order_dao
from backend.app.payment.schema.my_orders import MyOrderItem, MyOrderQuery
from backend.app.payment.service import my_order_service as service_module
from backend.app.payment.service.my_order_service import MyOrderService
from backend.common.exception import errors
from backend.utils.timezone import timezone


def test_query_validates_status_dates_and_page_bounds() -> None:
    for data in (
        {'status': 'bad'},
        {'page': 0},
        {'page_size': 101},
        {'created_from': '2026-10-10', 'created_to': '2026-10-01'},
        {'created_to': '9999-12-31'},
    ):
        with pytest.raises(ValidationError):
            MyOrderQuery(**data)
    assert MyOrderQuery(status='refund').status == 'refund'


def test_my_order_api_documents_query_fields_and_authenticated_routes() -> None:
    from fastapi import FastAPI

    from backend.app.payment.api.v1.my_orders import router

    app = FastAPI()
    app.include_router(router)
    schema = app.openapi()
    params = {item['name'] for item in schema['paths']['/pay/orders/my/page']['get']['parameters']}
    assert {'status', 'keyword', 'biz_type', 'pay_type', 'created_from', 'created_to', 'page', 'page_size'} <= params
    assert len(router.dependencies) == 1
    assert 'delete' in schema['paths']['/pay/orders/my/{order_no}']


def test_postgres_query_filters_pagination_and_visibility() -> None:
    """编译真实 PostgreSQL 查询并校验边界，不连接数据库或新增 SQLite 依赖。"""

    async def run() -> None:
        db = SimpleNamespace(
            scalar=AsyncMock(return_value=5),
            execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=list))),
        )
        _, total = await pay_order_dao.get_user_page(
            db,
            7,
            MyOrderQuery(
                status='refund',
                keyword='%_',
                biz_type='subscription_template',
                pay_type='virtual',
                created_from='2026-10-09',
                created_to='2026-10-09',
                page=2,
                page_size=2,
            ),
        )
        assert total == 5
        stmt = db.execute.call_args.args[0]
        sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
        assert 'pay_order.user_id = 7' in sql
        assert "pay_order.status IN ('refund_pending', 'refunded')" in sql
        assert "pay_order.biz_type = 'subscription_template'" in sql
        assert "pay_order.pay_type = 'virtual'" in sql
        assert '2026-10-09 00:00:00' in sql and '2026-10-10 00:00:00' in sql
        assert 'pay_order.created_time < ' in sql
        assert 'LIMIT 2 OFFSET 2' in sql
        assert 'ORDER BY pay_order.created_time DESC, pay_order.id DESC' in sql
        assert '/%/_' in stmt.compile().params.values()
        # 非终态必须重新可见，迟到付款不能被此前删除动作遮住。
        assert "pay_order.user_hidden_at IS NULL OR (pay_order.status NOT IN ('closed', 'refunded'))" in sql
        count_sql = str(db.scalar.call_args.args[0].compile(dialect=postgresql.dialect()))
        assert 'LIMIT' not in count_sql and 'user_id' in count_sql
        await pay_order_dao.get_by_user(db, 7)
        assert 'user_hidden_at IS NULL' in str(db.execute.call_args.args[0])

    asyncio.run(run())


def test_filter_options_remain_scoped_to_current_user() -> None:
    db = SimpleNamespace(
        scalars=AsyncMock(
            side_effect=[
                SimpleNamespace(all=lambda: ['subscription_template']),
                SimpleNamespace(all=lambda: ['virtual']),
            ]
        )
    )
    result = asyncio.run(pay_order_dao.get_user_filter_options(db, 7))
    assert result == (['subscription_template'], ['virtual'])
    for call in db.scalars.call_args_list:
        sql = str(call.args[0].compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
        assert 'pay_order.user_id = 7' in sql and 'user_hidden_at IS NULL' in sql


@pytest.mark.parametrize('status', ['pending', 'paid', 'refund_pending'])
def test_active_orders_cannot_be_hidden(monkeypatch: pytest.MonkeyPatch, status: str) -> None:
    _, _, updates, _, _ = install_close(monkeypatch, status=status)
    with pytest.raises(errors.RequestError):
        asyncio.run(MyOrderService.remove(None, 7, 'O'))
    assert updates == []


@pytest.mark.parametrize('status', ['closed', 'refunded'])
def test_user_hide_only_updates_visibility_and_is_idempotent(monkeypatch: pytest.MonkeyPatch, status: str) -> None:
    order, _, updates, _, _ = install_close(monkeypatch, status=status)
    with pytest.raises(errors.NotFoundError):
        asyncio.run(MyOrderService.remove(None, 8, 'O'))
    asyncio.run(MyOrderService.remove(None, 7, 'O'))
    asyncio.run(MyOrderService.remove(None, 7, 'O'))
    assert len(updates) == 1 and set(updates[0]) == {'user_hidden_at'}
    assert order.status == status and order.amount == Decimal('4.90')
    assert order.extra_data == {'tier_code': 'SVIP', 'openid': 'private'}
    service_module.pay_transaction_dao.update_model.assert_not_awaited()


def install_close(monkeypatch: pytest.MonkeyPatch, *, pay_type: str = 'virtual', status: str = 'pending') -> tuple:
    order = SimpleNamespace(
        id=1,
        order_no='O',
        user_id=7,
        biz_type='subscription_template',
        item_code='m',
        item_name='月卡',
        amount=Decimal('4.90'),
        pay_type=pay_type,
        status=status,
        fulfill_status='pending',
        trade_no=None,
        transaction_no='T',
        created_time=timezone.now(),
        paid_time=None,
        fulfilled_time=None,
        refunded_time=None,
        closed_time=None,
        user_hidden_at=None,
        extra_data={'tier_code': 'SVIP', 'openid': 'private'},
    )
    txn = SimpleNamespace(id=2, user_id=7, status='pending')
    updates = []

    def update_order(_db: Any, _id: int, data: dict[str, Any]) -> None:
        updates.append(data)
        for key, value in data.items():
            setattr(order, key, value)

    monkeypatch.setattr(service_module.pay_order_dao, 'get_by_order_no', AsyncMock(return_value=order))
    monkeypatch.setattr(service_module.pay_transaction_dao, 'get_by_order_no', AsyncMock(return_value=txn))
    monkeypatch.setattr(service_module.pay_order_dao, 'update_model', AsyncMock(side_effect=update_order))
    monkeypatch.setattr(service_module.pay_transaction_dao, 'update_model', AsyncMock())
    refresh = AsyncMock(side_effect=lambda *args: MyOrderService.present(order))
    monkeypatch.setattr(MyOrderService, 'refresh', refresh)
    provider = SimpleNamespace(close=AsyncMock())
    monkeypatch.setattr(service_module, 'get_provider', lambda _: provider)
    return order, txn, updates, refresh, provider


@pytest.mark.parametrize('pay_type', ['virtual', 'hupijiao'])
def test_non_remote_channels_close_only_local_record(monkeypatch: pytest.MonkeyPatch, pay_type: str) -> None:
    order, _, updates, refresh, provider = install_close(monkeypatch, pay_type=pay_type)
    result = asyncio.run(MyOrderService.close(None, 7, 'O'))
    assert result.status == 'closed' and result.close_kind == 'local'
    assert result.can_remove is True
    assert 'extra_data' not in result.model_dump() and result.tier_code == 'SVIP'
    assert order.user_hidden_at is None
    refresh.assert_awaited_once()
    provider.close.assert_not_awaited()
    assert updates[0]['status'] == 'closed'


def test_close_does_not_overwrite_payment_observed_during_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    order, _, updates, refresh, provider = install_close(monkeypatch)

    def paid(*_args: Any) -> MyOrderItem:
        order.status = 'paid'
        return MyOrderService.present(order)

    refresh.side_effect = paid
    result = asyncio.run(MyOrderService.close(None, 7, 'O'))
    assert result.status == 'paid' and updates == []
    provider.close.assert_not_awaited()


def test_close_checks_owner_before_querying_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, updates, refresh, provider = install_close(monkeypatch)
    with pytest.raises(errors.NotFoundError):
        asyncio.run(MyOrderService.close(None, 8, 'O'))
    refresh.assert_not_awaited()
    provider.close.assert_not_awaited()
    assert updates == []


def test_remote_close_failure_does_not_claim_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, updates, _, provider = install_close(monkeypatch, pay_type='jsapi')
    provider.close.side_effect = RuntimeError('channel unavailable')
    with pytest.raises(RuntimeError):
        asyncio.run(MyOrderService.close(None, 7, 'O'))
    assert updates == []
    service_module.pay_transaction_dao.update_model.assert_not_awaited()


def test_failed_status_query_does_not_close_record(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, updates, refresh, provider = install_close(monkeypatch)
    refresh.side_effect = RuntimeError('offline')
    with pytest.raises(RuntimeError):
        asyncio.run(MyOrderService.close(None, 7, 'O'))
    assert updates == []
    provider.close.assert_not_awaited()
