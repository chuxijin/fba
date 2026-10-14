"""显式启用的开发库并发测试：只创建并清理本次随机临时 schema。"""

import asyncio
import os

from collections.abc import Awaitable, Callable
from datetime import timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from backend.app.access.constants import CommonStatus, SubscriptionSource, SubscriptionStatus, TemplateKind
from backend.app.access.model.pack import EntitlementPack, PackItem
from backend.app.access.model.subscription import Subscription
from backend.app.access.model.template import SubscriptionTemplate, TemplatePack
from backend.app.access.model.tier import MembershipTier
from backend.app.access.service.sale_snapshot_service import sale_snapshot_service
from backend.app.access.service.subscription_service import subscription_service
from backend.app.payment.model.group_buy import (
    PayGroupBuyActivity,
    PayGroupBuyMember,
    PayGroupBuyTask,
    PayGroupBuyTeam,
    PayGroupBuyTier,
)
from backend.app.payment.model.pay_order import PayOrder
from backend.app.payment.model.pay_transaction import PayTransaction
from backend.app.payment.schema.group_buy import GroupBuyPrepayParam
from backend.app.payment.service.group_buy_service import group_buy_service
from backend.app.payment.service.group_buy_worker import group_buy_worker
from backend.app.payment.service.pay_service import pay_service
from backend.core.conf import settings
from backend.database.db import get_database_url
from backend.utils.timezone import timezone

pytestmark = pytest.mark.skipif(
    os.getenv('GROUP_BUY_PG_TEST') != '1', reason='设置 GROUP_BUY_PG_TEST=1 才运行开发库临时 schema 测试'
)


async def in_isolated_schema(scenario: Callable[..., Awaitable[None]], *, include_access: bool = False) -> None:
    if settings.ENVIRONMENT != 'dev' or settings.DATABASE_TYPE != 'postgresql':
        raise RuntimeError('仅允许在 PostgreSQL 开发环境运行')
    schema = f'gb_test_{uuid4().hex}'
    bootstrap = create_async_engine(get_database_url())
    engine = None
    created = False
    try:
        async with bootstrap.begin() as connection:
            await connection.execute(CreateSchema(schema))
        created = True
        engine = create_async_engine(get_database_url(), connect_args={'server_settings': {'search_path': schema}})
        tables = [
            m.__table__
            for m in [
                PayOrder,
                PayTransaction,
                PayGroupBuyActivity,
                PayGroupBuyTier,
                PayGroupBuyTeam,
                PayGroupBuyMember,
                PayGroupBuyTask,
            ]
        ]
        async with engine.begin() as connection:
            if include_access:
                await connection.run_sync(
                    lambda conn: ENUM('active', 'archived', 'draft', name='common_status').create(conn)
                )
                await connection.run_sync(
                    lambda conn: ENUM('standard', 'bundle', 'trial', 'gift', 'corporate', name='template_kind').create(
                        conn
                    )
                )
                tables.extend([
                    m.__table__
                    for m in [
                        MembershipTier,
                        SubscriptionTemplate,
                        TemplatePack,
                        EntitlementPack,
                        PackItem,
                        Subscription,
                    ]
                ])
                await connection.run_sync(
                    lambda conn: ENUM(*[e.value for e in SubscriptionSource], name='subscription_source').create(conn)
                )
                await connection.run_sync(
                    lambda conn: ENUM(*[e.value for e in SubscriptionStatus], name='subscription_status').create(conn)
                )
            for table in tables:
                await connection.run_sync(lambda conn, table=table: table.create(conn))
        maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        await scenario(maker)
    finally:
        if engine:
            await engine.dispose()
        if created:
            # 仅删除本函数已经成功创建的随机 schema，绝不引用业务 schema 名。
            async with bootstrap.begin() as connection:
                await connection.execute(DropSchema(schema, cascade=True))
        await bootstrap.dispose()


async def seed(maker: async_sessionmaker) -> tuple:
    now = timezone.now()
    async with maker.begin() as db:
        activity = PayGroupBuyActivity(
            name='并发测试',
            template_code='test',
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(days=1),
            rules={},
            status='active',
            created_by=1,
        )
        db.add(activity)
        await db.flush()
        snapshot = {
            'name': '测试活动',
            'template_code': 'test',
            'price_cents': 1000,
            'original_price_cents': 2000,
            'activity_end': (now + timedelta(days=1)).isoformat(),
            'team_seconds': 3600,
            'reservation_seconds': 300,
            'max_participations_per_user': 1,
            'channels': ['hupijiao'],
            'base': {'name': '套餐'},
            'rewards': {'member_rewards': [{'name': '奖励'}], 'leader_rewards': []},
        }
        team = PayGroupBuyTeam(
            activity_id=activity.id,
            leader_user_id=1,
            share_code=uuid4().hex[:24],
            request_key=uuid4().hex,
            people=3,
            snapshot=snapshot,
            draft_until=now + timedelta(minutes=5),
            status='forming',
            deadline=now + timedelta(hours=1),
            created_by=1,
        )
        db.add(team)
        await db.flush()
        return activity.id, team.id, team.share_code


def test_postgres_last_slot_allows_one_reservation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'PAYMENT_GROUP_BUY_ENABLE', True)
    monkeypatch.setattr(settings, 'PAYMENT_GROUP_BUY_CHANNELS', ['hupijiao'])

    async def scenario(maker: async_sessionmaker) -> None:
        activity_id, team_id, code = await seed(maker)
        async with maker.begin() as db:
            for user in (1, 2):
                db.add(
                    PayGroupBuyMember(
                        activity_id=activity_id,
                        team_id=team_id,
                        user_id=user,
                        reserved_until=timezone.now(),
                        status='paid',
                    )
                )

        async def reserve(user: int) -> bool:
            try:
                async with maker.begin() as db:
                    await group_buy_service.reserve_order(
                        db, code=code, user_id=user, obj=GroupBuyPrepayParam(pay_type='hupijiao')
                    )
            except Exception as error:
                assert '名额' in str(error)
                return False
            else:
                return True

        results = await asyncio.gather(*(reserve(user) for user in (3, 4, 5, 6)))
        assert sum(results) == 1
        async with maker() as db:
            count = await db.scalar(
                select(func.count()).select_from(PayGroupBuyMember).where(PayGroupBuyMember.team_id == team_id)
            )
            assert count == 3

    asyncio.run(in_isolated_schema(scenario))


def test_postgres_duplicate_payment_creates_one_business_task() -> None:
    async def scenario(maker: async_sessionmaker) -> None:
        _activity_id, team_id, _code = await seed(maker)
        now = timezone.now()
        async with maker.begin() as db:
            order = PayOrder(
                order_no=f'TEST{uuid4().hex[:12]}',
                user_id=3,
                biz_type='subscription_template',
                item_code='test',
                item_name='套餐',
                amount=Decimal('10.00'),
                pay_type='hupijiao',
                purchase_mode='group_buy',
                extra_data={'group_buy_team_id': team_id},
                created_by=3,
            )
            db.add(order)
            await db.flush()
            txn = PayTransaction(
                transaction_no=uuid4().hex,
                order_no=order.order_no,
                user_id=3,
                pay_type='hupijiao',
                amount=order.amount,
                biz_type=order.biz_type,
                created_by=3,
            )
            db.add(txn)
            await db.flush()
            txn_id, order_no = txn.id, order.order_no

        async def confirm() -> None:
            async with maker.begin() as db:
                await pay_service._mark_payment_success(
                    db=db, txn_id=txn_id, order_no=order_no, trade_no='CONFIRMED', paid_time=now, notify_data={}
                )

        results = await asyncio.gather(confirm(), confirm(), confirm(), return_exceptions=True)
        assert not any(isinstance(r, Exception) for r in results), results
        async with maker() as db:
            rows = list((await db.scalars(select(PayGroupBuyTask))).all())
            assert len(rows) == 1
            assert rows[0].kind == 'payment'
            current = (await db.scalars(select(PayOrder).where(PayOrder.order_no == order_no))).one()
            assert current.status == 'paid'
            assert current.fulfill_status == 'pending'

    asyncio.run(in_isolated_schema(scenario))


def test_postgres_concurrent_final_confirm_grants_once() -> None:
    async def scenario(maker: async_sessionmaker) -> None:
        activity_id, team_id, code = await seed(maker)
        now = timezone.now()
        async with maker.begin() as db:
            for user in (1, 2, 3):
                order = PayOrder(
                    order_no=f'TEST{uuid4().hex[:12]}',
                    user_id=user,
                    biz_type='subscription_template',
                    item_code='test',
                    item_name='套餐',
                    amount=Decimal('10.00'),
                    pay_type='hupijiao',
                    purchase_mode='group_buy',
                    status='paid',
                    paid_time=now,
                    created_by=user,
                )
                db.add(order)
                await db.flush()
                member = PayGroupBuyMember(
                    team_id=team_id,
                    activity_id=activity_id,
                    user_id=user,
                    order_id=order.id,
                    reserved_until=now + timedelta(minutes=5),
                    status='paid' if user < 3 else 'reserved',
                )
                db.add(member)
                await db.flush()
                order.extra_data = {
                    'group_buy_member_id': member.id,
                    'group_buy_reserved_until': member.reserved_until.isoformat(),
                }
                final_id = order.id

        async def confirm() -> None:
            async with maker.begin() as db:
                order = (await db.scalars(select(PayOrder).where(PayOrder.id == final_id).with_for_update())).one()
                team = (
                    await db.scalars(
                        select(PayGroupBuyTeam).where(PayGroupBuyTeam.share_code == code).with_for_update()
                    )
                ).one()
                await group_buy_worker._payment(db, order, team)

        results = await asyncio.gather(confirm(), confirm(), return_exceptions=True)
        assert not any(isinstance(r, Exception) for r in results), results
        async with maker() as db:
            team = await db.get(PayGroupBuyTeam, team_id)
            assert team.status == 'succeeded'
            tasks = list((await db.scalars(select(PayGroupBuyTask))).all())
            assert len(tasks) == 6
            assert len({t.key for t in tasks}) == 6

    asyncio.run(in_isolated_schema(scenario))


def test_postgres_frozen_template_survives_original_pack_change() -> None:
    async def scenario(maker: async_sessionmaker) -> None:
        async with maker.begin() as db:
            template = SubscriptionTemplate(
                code='original', name='原套餐', duration_days=30, price_cents=2000, kind=TemplateKind.STANDARD
            )
            pack = EntitlementPack(code='original_pack', name='原权益包')
            db.add_all([template, pack])
            await db.flush()
            item = PackItem(
                pack_id=pack.id, entitlement_id=42, value_int=10, value_meta={'quota': 10}, status=CommonStatus.ACTIVE
            )
            db.add_all([TemplatePack(template_id=template.id, pack_id=pack.id), item])
            await db.flush()
            snapshot = await sale_snapshot_service.capture(db, template)
            frozen = await sale_snapshot_service.materialize(db, snapshot)
            again = await sale_snapshot_service.materialize(db, snapshot)
            assert again.id == frozen.id
            item.value_int = 100
            template.duration_days = 99
            frozen_id = frozen.id
        async with maker() as db:
            frozen = await db.get(SubscriptionTemplate, frozen_id)
            assert frozen.duration_days == 30
            items = (
                await db.scalars(
                    select(PackItem)
                    .join(TemplatePack, TemplatePack.pack_id == PackItem.pack_id)
                    .where(TemplatePack.template_id == frozen_id)
                )
            ).all()
            assert len(items) == 1
            assert items[0].value_int == 10

    asyncio.run(in_isolated_schema(scenario, include_access=True))


def test_postgres_full_grant_retry_and_refund_revoke(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.question_bank.service.user_message_service import user_message_service

    monkeypatch.setattr(type(subscription_service), '_invalidate_user_access_cache', AsyncMock())
    monkeypatch.setattr(user_message_service, 'create', AsyncMock())

    async def scenario(maker: async_sessionmaker) -> None:
        monkeypatch.setattr('backend.app.payment.service.group_buy_worker.async_db_session', maker)
        activity_id, team_id, _code = await seed(maker)
        now = timezone.now()
        async with maker.begin() as db:
            template = SubscriptionTemplate(code='test', name='测试套餐', duration_days=30, price_cents=2000)
            pack = EntitlementPack(code='test_pack', name='权益包')
            db.add_all([template, pack])
            await db.flush()
            db.add_all([
                TemplatePack(template_id=template.id, pack_id=pack.id),
                PackItem(pack_id=pack.id, entitlement_id=42, value_int=10),
            ])
            await db.flush()
            base = await sale_snapshot_service.capture(db, template)
            reward = await sale_snapshot_service.capture(db, template, duration_days=3)
            team = await db.get(PayGroupBuyTeam, team_id)
            team.snapshot = {
                **team.snapshot,
                'base': base,
                'rewards': {'member_rewards': [reward], 'leader_rewards': []},
            }
            first_order_no = ''
            for user in (1, 2, 3):
                order = PayOrder(
                    order_no=f'TEST{uuid4().hex[:12]}',
                    user_id=user,
                    biz_type='subscription_template',
                    item_code='test',
                    item_name='套餐',
                    amount=Decimal('10.00'),
                    pay_type='hupijiao',
                    purchase_mode='group_buy',
                    status='paid',
                    trade_no=f'TRADE{user}',
                    paid_time=now,
                    created_by=user,
                )
                db.add(order)
                await db.flush()
                member = PayGroupBuyMember(
                    team_id=team_id,
                    activity_id=activity_id,
                    user_id=user,
                    order_id=order.id,
                    reserved_until=now + timedelta(minutes=5),
                )
                db.add(member)
                await db.flush()
                order.extra_data = {
                    'group_buy_team_id': team_id,
                    'group_buy_member_id': member.id,
                    'group_buy_reserved_until': member.reserved_until.isoformat(),
                }
                db.add(
                    PayTransaction(
                        transaction_no=uuid4().hex,
                        order_no=order.order_no,
                        user_id=user,
                        pay_type='hupijiao',
                        amount=order.amount,
                        biz_type=order.biz_type,
                        status='paid',
                        trade_no=order.trade_no,
                        paid_time=now,
                        created_by=user,
                    )
                )
                await group_buy_worker.payment_event(db, order)
                if user == 1:
                    first_order_no = order.order_no
        await group_buy_worker.drain()
        await group_buy_worker.drain()
        async with maker() as db:
            orders = list((await db.scalars(select(PayOrder))).all())
            assert all(o.fulfill_status == 'fulfilled' for o in orders)
            subs = list((await db.scalars(select(Subscription))).all())
            assert len(subs) == 6
            base_sub = next(s for s in subs if s.source_ref == first_order_no)
            reward_sub = next(s for s in subs if s.parent_subscription_id == base_sub.id)
            assert reward_sub.valid_period.lower == base_sub.valid_period.upper
            assert (reward_sub.valid_period.upper - reward_sub.valid_period.lower).days == 3
            tasks = list((await db.scalars(select(PayGroupBuyTask))).all())
            assert all(t.status == 'done' for t in tasks)
        async with maker.begin() as db:
            txn = (await db.scalars(select(PayTransaction).where(PayTransaction.order_no == first_order_no))).one()
            await pay_service._mark_refund_result(db=db, txn_id=txn.id, data={'refund_status': 'SUCCESS'})
        await group_buy_worker.drain()
        async with maker() as db:
            orders = list((await db.scalars(select(PayOrder))).all())
            refunded = next(o for o in orders if o.order_no == first_order_no)
            assert refunded.status == 'refunded' and refunded.fulfill_status == 'revoked'
            subs = list((await db.scalars(select(Subscription))).all())
            assert all(s.status == SubscriptionStatus.REFUNDED for s in subs if s.user_id == 1)
            assert all(s.status == SubscriptionStatus.ACTIVE for s in subs if s.user_id != 1)

    asyncio.run(in_isolated_schema(scenario, include_access=True))


if __name__ == '__main__':
    os.environ['GROUP_BUY_PG_TEST'] = '1'
    raise SystemExit(pytest.main([__file__, '-q', '--disable-warnings', '--tb=short']))
