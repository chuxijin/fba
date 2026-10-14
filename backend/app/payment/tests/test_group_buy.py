#!/usr/bin/env python3
import asyncio

from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from backend.app.access.constants import CommonStatus, TemplateKind
from backend.app.access.service.sale_snapshot_service import ensure_sale_snapshot_writable, sale_snapshot_service
from backend.app.payment.model.group_buy import PayGroupBuyMember, PayGroupBuyTask
from backend.app.payment.schema.group_buy import GroupBuyActivityParam
from backend.app.payment.service.group_buy_worker import accepts_payment, group_buy_worker
from backend.app.payment.service.subscription_notifier import subscription_payment_notifier
from backend.utils.timezone import timezone


def activity_params() -> dict:
    now = timezone.now()
    return {
        'name': '测试活动',
        'template_code': 'test',
        'starts_at': now,
        'ends_at': now + timedelta(days=2),
        'team_seconds': 3600,
        'reservation_seconds': 300,
        'max_participations_per_user': 1,
        'reward_stack_policy': 'independent',
        'channels': ['hupijiao'],
        'tiers': [
            {
                'people': 3,
                'price_cents': 1200,
                'member_rewards': [{'template_code': 'test', 'duration_days': 3}],
                'leader_rewards': [],
            }
        ],
    }


@pytest.mark.parametrize(
    'change',
    [
        {'tiers': []},
        {'reservation_seconds': 7200},
        {'reward_stack_policy': 'unknown'},
        {'channels': ['virtual']},
        {'tiers': [{'people': 2, 'price_cents': 100, 'member_rewards': [], 'leader_rewards': []}]},
    ],
)
def test_activity_rejects_invalid_or_incomplete_sale_rules(change: dict) -> None:
    with pytest.raises(ValidationError):
        GroupBuyActivityParam(**{**activity_params(), **change})


def test_activity_accepts_explicit_configuration() -> None:
    obj = GroupBuyActivityParam(**activity_params())
    assert obj.tiers[0].people == 3
    assert obj.tiers[0].price_cents == 1200


@pytest.mark.parametrize('state', ['succeeded', 'expired', 'cancelled'])
def test_terminal_team_never_reopens(state: str) -> None:
    now = timezone.now()
    assert not accepts_payment(
        team_status=state,
        matches_order=True,
        paid_at=now,
        reserved_until=now + timedelta(seconds=1),
        deadline=now + timedelta(hours=1),
        occupied_by_others=2,
        people=3,
    )


def test_payment_capacity_and_original_order_are_required() -> None:
    now = timezone.now()
    args = {
        'team_status': 'forming',
        'matches_order': True,
        'paid_at': now,
        'reserved_until': now + timedelta(seconds=1),
        'deadline': now + timedelta(hours=1),
        'occupied_by_others': 2,
        'people': 3,
    }
    assert accepts_payment(**args)
    for change in [{'matches_order': False}, {'occupied_by_others': 3}, {'paid_at': now + timedelta(seconds=2)}]:
        assert not accepts_payment(**{**args, **change})


def payment_objects(people: int = 3) -> tuple:
    now = timezone.now()
    members = [
        SimpleNamespace(id=i, order_id=10 + i, user_id=i, status='reserved', reserved_until=now + timedelta(minutes=5))
        for i in range(1, people + 1)
    ]
    team = SimpleNamespace(
        id=1,
        activity_id=1,
        people=people,
        leader_user_id=1,
        status='draft',
        deadline=None,
        succeeded_at=None,
        snapshot={
            'team_seconds': 3600,
            'max_participations_per_user': 1,
            'activity_end': (now + timedelta(days=1)).isoformat(),
            'base': {'name': '套餐'},
            'rewards': {'member_rewards': [{'name': '成员奖励'}], 'leader_rewards': [{'name': '团长奖励'}]},
        },
    )
    orders = [
        SimpleNamespace(
            id=m.order_id,
            order_no=f'TEST{m.id}',
            user_id=m.user_id,
            status='paid',
            paid_time=now,
            fulfill_status='pending',
            closed_time=None,
            extra_data={'group_buy_member_id': m.id, 'group_buy_reserved_until': m.reserved_until.isoformat()},
        )
        for m in members
    ]
    return members, team, orders


def test_five_person_team_only_succeeds_at_five_confirmed_payments(monkeypatch: pytest.MonkeyPatch) -> None:
    members, team, orders = payment_objects(5)
    db = SimpleNamespace(flush=AsyncMock(), scalar=AsyncMock(return_value=0))
    monkeypatch.setattr(
        'backend.app.payment.service.group_buy_worker.group_buy_dao.members', AsyncMock(return_value=members)
    )
    enqueue = AsyncMock()
    monkeypatch.setattr('backend.app.payment.service.group_buy_worker.group_buy_dao.enqueue', enqueue)

    async def scenario() -> None:
        for order in orders[:3]:
            await group_buy_worker._payment(db, order, team)
        assert team.status == 'forming'
        assert sum(m.status == 'paid' for m in members) == 3
        assert enqueue.await_count == 0
        assert all(o.fulfill_status == 'pending' for o in orders)
        await group_buy_worker._payment(db, orders[0], team)
        assert sum(m.status == 'paid' for m in members) == 3
        for order in orders[3:]:
            await group_buy_worker._payment(db, order, team)
        assert team.status == 'succeeded'
        assert enqueue.await_count == 11  # 5 个套餐 + 5 个成员奖励 + 1 个团长奖励。
        await group_buy_worker._payment(db, orders[-1], team)
        assert enqueue.await_count == 11

    asyncio.run(scenario())


@pytest.mark.parametrize('invalid', ['expired_team', 'old_order', 'late_payment', 'closed_order'])
def test_invalid_real_payment_is_refunded_without_counting(monkeypatch: pytest.MonkeyPatch, invalid: str) -> None:
    members, team, orders = payment_objects()
    order = orders[0]
    if invalid == 'expired_team':
        team.status = 'expired'
    elif invalid == 'old_order':
        members[0].order_id += 100
    elif invalid == 'late_payment':
        order.paid_time += timedelta(hours=1)
    else:
        order.closed_time = timezone.now()
    monkeypatch.setattr(
        'backend.app.payment.service.group_buy_worker.group_buy_dao.members', AsyncMock(return_value=members)
    )
    refund = AsyncMock()
    monkeypatch.setattr(type(group_buy_worker), '_schedule_refund', refund)
    asyncio.run(group_buy_worker._payment(SimpleNamespace(flush=AsyncMock()), order, team))
    refund.assert_awaited_once()
    assert all(m.status != 'paid' for m in members)


def test_refunded_order_cannot_receive_base_or_reward() -> None:
    order = SimpleNamespace(status='refunded')
    for kind in ('base', 'reward'):
        task = SimpleNamespace(kind=kind, status='running', error=None)
        asyncio.run(group_buy_worker._grant(None, order, SimpleNamespace(status='succeeded'), task))
        assert task.status == 'done'
        assert '退款' in task.error


def test_refund_dispatch_uses_persisted_identity_and_does_not_repeat() -> None:
    task = SimpleNamespace(payload={'refund_no': 'STABLE'}, status='running', error=None)
    txn = SimpleNamespace(amount=Decimal('12.00'))
    order = SimpleNamespace(order_no='TEST', trade_no='TRADE', pay_type='hupijiao', extra_data={}, status='paid')
    outbound = group_buy_worker._prepare_refund(order, task, txn)
    assert outbound[3] == 'STABLE'
    assert txn.refund_no == 'STABLE'
    assert txn.status == order.status == 'refund_pending'
    assert group_buy_worker._prepare_refund(order, task, txn) is None
    assert task.status == 'manual_review'
    assert txn.refund_no == 'STABLE'


def test_group_payment_notifier_defers_subscription(monkeypatch: pytest.MonkeyPatch) -> None:
    order = SimpleNamespace(id=1, purchase_mode='group_buy', biz_type='subscription_template')
    monkeypatch.setattr(
        'backend.app.payment.service.subscription_notifier.pay_order_dao.get_by_order_no', AsyncMock(return_value=order)
    )
    event = AsyncMock()
    monkeypatch.setattr(group_buy_worker, 'payment_event', event)
    grant = AsyncMock()
    monkeypatch.setattr(
        'backend.app.payment.service.subscription_notifier.subscription_service.create_from_template', grant
    )
    asyncio.run(
        subscription_payment_notifier.on_payment_success(
            db=None, order_no='TEST', trade_no='T', paid_amount=Decimal('12.00')
        )
    )
    event.assert_awaited_once()
    grant.assert_not_awaited()


def test_sale_snapshot_deepcopies_values() -> None:
    template = SimpleNamespace(
        id=1, code='original', name='套餐', tier_id=1, duration_days=30, kind=TemplateKind.STANDARD, cover_image=None
    )
    pack = SimpleNamespace(id=1, name='权益包', domain_id=1, description='', status=CommonStatus.ACTIVE)
    item = SimpleNamespace(entitlement_id=1, value_int=10, value_meta={'nested': {'quota': 5}})

    def result(values: list) -> SimpleNamespace:
        return SimpleNamespace(all=lambda: values)

    db = SimpleNamespace(scalars=AsyncMock(side_effect=[result([pack]), result([item])]))
    snapshot = asyncio.run(sale_snapshot_service.capture(db, template))
    original = deepcopy(snapshot)
    item.value_meta['nested']['quota'] = 100
    assert snapshot == original
    with pytest.raises(Exception):
        ensure_sale_snapshot_writable('GBS_frozen')


def test_postgresql_constraints_enforce_member_and_task_uniqueness() -> None:
    ddl = str(CreateTable(PayGroupBuyMember.__table__).compile(dialect=postgresql.dialect()))
    assert 'UNIQUE (team_id, user_id)' in ddl
    assert 'UNIQUE (order_id)' in ddl
    task_ddl = str(CreateTable(PayGroupBuyTask.__table__).compile(dialect=postgresql.dialect()))
    assert 'UNIQUE (key)' in task_ddl
