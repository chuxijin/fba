#!/usr/bin/env python3
"""数据库任务表驱动拼团交易；所有外部退款先记录派发意图，再离开事务调用。"""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import SubscriptionSource
from backend.app.access.model.subscription import Subscription
from backend.app.access.service.sale_snapshot_service import sale_snapshot_service
from backend.app.access.service.subscription_service import subscription_service
from backend.app.payment.crud.crud_group_buy import group_buy_dao
from backend.app.payment.crud.crud_pay_order import pay_order_dao
from backend.app.payment.crud.crud_pay_transaction import pay_transaction_dao
from backend.app.payment.model.group_buy import PayGroupBuyActivity, PayGroupBuyTask, PayGroupBuyTeam
from backend.app.payment.model.pay_order import PayOrder
from backend.app.payment.model.pay_transaction import PayTransaction
from backend.app.payment.service.pay_service import pay_service
from backend.common.exception import errors
from backend.common.log import log
from backend.common.payment import get_provider
from backend.database.db import async_db_session
from backend.utils.timezone import timezone


def accepts_payment(
    *,
    team_status: str,
    matches_order: bool,
    paid_at: datetime,
    reserved_until: datetime,
    deadline: datetime | None,
    occupied_by_others: int,
    people: int,
) -> bool:
    """渠道付款时间符合原占位且还有实际名额；终态不能重新开启。"""
    return (
        team_status in ('draft', 'forming')
        and matches_order
        and paid_at <= reserved_until
        and (deadline is None or paid_at <= deadline)
        and occupied_by_others < people
    )


class GroupBuyWorker:
    @staticmethod
    async def payment_event(db: AsyncSession, order: PayOrder) -> None:
        await group_buy_dao.enqueue(
            db,
            key=f'gb:payment:{order.order_no}',
            kind='payment',
            team_id=order.extra_data['group_buy_team_id'],
            order_id=order.id,
        )

    @staticmethod
    async def refund_event(db: AsyncSession, order: PayOrder) -> None:
        await group_buy_dao.enqueue(
            db,
            key=f'gb:settle:{order.order_no}',
            kind='refund',
            team_id=order.extra_data['group_buy_team_id'],
            order_id=order.id,
            payload={'settle_only': True},
        )

    @staticmethod
    async def _schedule_refund(db: AsyncSession, team: PayGroupBuyTeam, order: PayOrder) -> None:
        if order.status == 'refunded':
            return
        order.status = 'refund_pending'
        order.user_hidden_at = None
        await group_buy_dao.enqueue(
            db,
            key=f'gb:refund:{order.order_no}',
            kind='refund',
            team_id=team.id,
            order_id=order.id,
            payload={'refund_no': pay_service._generate_refund_no()},
        )
        for member in await group_buy_dao.members(db, team.id):
            if member.order_id == order.id:
                member.status = 'refund_pending'
        await db.flush()

    @staticmethod
    async def _payment(db: AsyncSession, order: PayOrder, team: PayGroupBuyTeam) -> None:
        if order.status in ('refund_pending', 'refunded'):
            return
        if order.status != 'paid':
            raise errors.RequestError(msg='付款事实尚未确认')
        members = await group_buy_dao.members(db, team.id)
        member = next((m for m in members if m.id == order.extra_data.get('group_buy_member_id')), None)
        if member and member.order_id == order.id and member.status == 'paid':
            return
        now = timezone.now()
        occupied = sum(
            m.status == 'paid' or (m.status == 'reserved' and m.reserved_until > now) for m in members if m != member
        )
        until = datetime.fromisoformat(order.extra_data['group_buy_reserved_until'])
        valid = accepts_payment(
            team_status=team.status,
            matches_order=bool(member and member.order_id == order.id and order.closed_time is None),
            paid_at=order.paid_time or now,
            reserved_until=until,
            deadline=team.deadline,
            occupied_by_others=occupied,
            people=team.people,
        )
        if not valid:
            await GroupBuyWorker._schedule_refund(db, team, order)
            return
        from backend.app.payment.service.group_buy_service import group_buy_service

        try:
            await group_buy_service._check_participation(
                db,
                team.activity_id,
                order.user_id,
                team.snapshot['max_participations_per_user'],
                excluding_member=member.id,
            )
        except errors.ForbiddenError:
            await GroupBuyWorker._schedule_refund(db, team, order)
            return
        member.status, member.paid_at = 'paid', order.paid_time or now
        if team.status == 'draft':
            if member.user_id != team.leader_user_id:
                await GroupBuyWorker._schedule_refund(db, team, order)
                return
            team.status = 'forming'
            team.started_at = member.paid_at
            team.deadline = min(
                member.paid_at + timedelta(seconds=team.snapshot['team_seconds']),
                datetime.fromisoformat(team.snapshot['activity_end']),
            )
        await db.flush()
        if sum(m.status == 'paid' for m in members) != team.people:
            return
        await GroupBuyWorker._complete_team(db, team, members, now)

    @staticmethod
    async def _complete_team(db: AsyncSession, team: PayGroupBuyTeam, members: list, now: datetime) -> None:
        team.status, team.succeeded_at = 'succeeded', now
        # 不在最后付款订单的锁内同步锁其他订单或调用渠道；只保存独立任务。
        for paid in members:
            if paid.status != 'paid':
                continue
            await group_buy_dao.enqueue(
                db,
                key=f'gb:base:{paid.order_id}',
                kind='base',
                team_id=team.id,
                order_id=paid.order_id,
                payload={'snapshot': team.snapshot['base']},
            )
            rewards = [*team.snapshot['rewards']['member_rewards']]
            if paid.user_id == team.leader_user_id:
                rewards.extend(team.snapshot['rewards']['leader_rewards'])
            for index, reward in enumerate(rewards):
                await group_buy_dao.enqueue(
                    db,
                    key=f'gb:reward:{paid.order_id}:{index}',
                    kind='reward',
                    team_id=team.id,
                    order_id=paid.order_id,
                    payload={'snapshot': reward},
                )
        await db.flush()

    @staticmethod
    async def _grant(db: AsyncSession, order: PayOrder, team: PayGroupBuyTeam, task: PayGroupBuyTask) -> None:
        if order.status != 'paid' or team.status != 'succeeded':
            if order.status in ('refund_pending', 'refunded'):
                task.status = 'done'
                task.error = '退款订单不发放权益'
                return
            raise errors.RequestError(msg='尚未成团或付款状态已改变')
        is_base = task.kind == 'base'
        if not is_base and order.fulfill_status != 'fulfilled':
            raise errors.RequestError(msg='等待基础套餐开通')
        ref = order.order_no if is_base else task.key
        existing = (
            await db.scalars(
                select(Subscription).where(
                    Subscription.user_id == order.user_id,
                    Subscription.source == SubscriptionSource.ORDER,
                    Subscription.source_ref == ref,
                )
            )
        ).first()
        if existing is None:
            snapshot = task.payload['snapshot']
            template = await sale_snapshot_service.materialize(db, snapshot)
            start_at = None
            parent_id = None
            if not is_base:
                base = (
                    await db.scalars(
                        select(Subscription).where(
                            Subscription.user_id == order.user_id,
                            Subscription.source == SubscriptionSource.ORDER,
                            Subscription.source_ref == order.order_no,
                        )
                    )
                ).one()
                parent_id = base.id
                # 同套餐的奖励追加时长；不同套餐按独立订阅生效。
                siblings = list(
                    (
                        await db.scalars(
                            select(Subscription).where(
                                Subscription.user_id == order.user_id,
                                (Subscription.id == base.id) | (Subscription.parent_subscription_id == base.id),
                            )
                        )
                    ).all()
                )
                ends = [
                    s.valid_period.upper
                    for s in siblings
                    if s.valid_period.upper and (s.metadata_ or {}).get('original_code') == snapshot['original_code']
                ]
                if ends:
                    start_at = max(timezone.now(), *ends)
            existing = await subscription_service.create_from_template(
                db,
                user_id=order.user_id,
                template_code=template.code,
                source=SubscriptionSource.ORDER,
                source_ref=ref,
                start_at=start_at,
                parent_subscription_id=parent_id,
                duration_days=snapshot['duration_days'],
            )
            existing.metadata_ = {
                'sale_snapshot': True,
                'original_code': snapshot['original_code'],
                'group_buy_team_id': team.id,
                'group_buy_task_key': task.key,
            }
        task.payload = {**task.payload, 'subscription_id': existing.id}
        if is_base:
            order.fulfill_status, order.fulfilled_time = 'fulfilled', timezone.now()
            order.extra_data = {**order.extra_data, 'subscription_id': existing.id}
            if order.pay_type == 'virtual':
                await group_buy_dao.enqueue(
                    db, key=f'gb:goods:{order.order_no}', kind='notify_goods', team_id=team.id, order_id=order.id
                )
        task.status = 'done'
        await db.flush()

    @staticmethod
    async def _settle_refund(db: AsyncSession, order: PayOrder, team: PayGroupBuyTeam) -> None:
        await subscription_service.revoke_by_source(
            db, user_id=order.user_id, source=SubscriptionSource.ORDER, source_ref=order.order_no, reason='拼团退款撤销'
        )
        tasks = (await db.scalars(select(PayGroupBuyTask).where(PayGroupBuyTask.order_id == order.id))).all()
        for task in tasks:
            if task.kind == 'reward':
                await subscription_service.revoke_by_source(
                    db,
                    user_id=order.user_id,
                    source=SubscriptionSource.ORDER,
                    source_ref=task.key,
                    reason='拼团退款撤销奖励',
                )
            task.status = 'done'
            task.lease_until = None
        order.fulfill_status = 'revoked'
        for member in await group_buy_dao.members(db, team.id):
            if member.order_id == order.id:
                member.status = 'refunded'
        await db.flush()

    @staticmethod
    async def execute(task_id: int, attempt: int) -> None:
        outbound = None
        # 虚拟支付付款推送不足以证明金额，计人数前从渠道核对本人订单。
        async with async_db_session() as db:
            initial_task = await db.get(PayGroupBuyTask, task_id)
            initial_order = await db.get(PayOrder, initial_task.order_id) if initial_task else None
        if (
            initial_task
            and initial_order
            and initial_task.kind == 'payment'
            and initial_order.pay_type == 'virtual'
            and initial_order.status == 'paid'
        ):
            await GroupBuyWorker._verify_virtual_order(initial_order)
        async with async_db_session.begin() as db:
            task = await db.get(PayGroupBuyTask, task_id)
            if not task:
                return
            order = await db.get(PayOrder, task.order_id)
            if not order:
                raise errors.NotFoundError(msg='任务订单不存在')
            # 与回调保持 txn -> order -> team -> task 顺序；领取租约已单独提交。
            txn = await pay_transaction_dao.get_by_order_no(db, order.order_no, for_update=True)
            order = await pay_order_dao.get_by_order_no(db, order.order_no, for_update=True)
            activity_id = await db.scalar(select(PayGroupBuyTeam.activity_id).where(PayGroupBuyTeam.id == task.team_id))
            await db.execute(
                select(PayGroupBuyActivity.id).where(PayGroupBuyActivity.id == activity_id).with_for_update()
            )
            team = (
                await db.scalars(
                    select(PayGroupBuyTeam)
                    .where(PayGroupBuyTeam.id == task.team_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).one()
            task = (
                await db.scalars(
                    select(PayGroupBuyTask)
                    .where(PayGroupBuyTask.id == task_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).one()
            if task.status != 'running' or task.attempts != attempt:
                return
            if order.status == 'refunded':
                await GroupBuyWorker._settle_refund(db, order, team)
                return
            outbound = await GroupBuyWorker._run_local(db, order, team, task, txn)
            task.lease_until = None if outbound is None else timezone.now() + timedelta(minutes=5)
        if outbound is None:
            return
        await GroupBuyWorker._send_outbound(task_id, attempt, outbound)

    @staticmethod
    async def _run_local(
        db: AsyncSession, order: PayOrder, team: PayGroupBuyTeam, task: PayGroupBuyTask, txn: PayTransaction | None
    ) -> tuple | None:
        if task.kind == 'payment':
            await GroupBuyWorker._payment(db, order, team)
            task.status = 'done'
        elif task.kind in ('base', 'reward'):
            await GroupBuyWorker._grant(db, order, team, task)
        elif task.kind == 'refund':
            return GroupBuyWorker._prepare_refund(order, task, txn)
        elif task.kind == 'notify_goods':
            if order.status != 'paid' or order.fulfill_status != 'fulfilled':
                task.status = 'done'
            else:
                return (
                    'notify_goods',
                    order.order_no,
                    order.pay_type,
                    '',
                    Decimal(0),
                    int(order.extra_data.get('env') or 0),
                )
        return None

    @staticmethod
    def _prepare_refund(order: PayOrder, task: PayGroupBuyTask, txn: PayTransaction | None) -> tuple | None:
        if task.payload.get('settle_only'):
            raise errors.RequestError(msg='退款渠道事实尚未确认')
        if task.payload.get('dispatch_started'):
            task.status = 'manual_review'
            task.error = '退款已派发，等待渠道回调或人工核实；禁止盲重发'
            return None
        if not txn or not order.trade_no:
            raise errors.RequestError(msg='缺少真实付款记录，不能退款')
        task.payload = {**task.payload, 'dispatch_started': True}
        txn.status, txn.refund_no, txn.refund_amount = 'refund_pending', task.payload['refund_no'], txn.amount
        order.status = 'refund_pending'
        return (
            'refund',
            order.order_no,
            order.pay_type,
            task.payload['refund_no'],
            txn.amount,
            int(order.extra_data.get('env') or 0),
        )

    @staticmethod
    async def _send_outbound(task_id: int, attempt: int, outbound: tuple) -> None:
        kind, order_no, pay_type, refund_no, amount, env = outbound
        provider = get_provider(pay_type)
        try:
            if kind == 'refund':
                result = await provider.refund(
                    order_no=order_no,
                    refund_no=refund_no,
                    total_fee=pay_service._yuan_to_fen(amount),
                    refund_fee=pay_service._yuan_to_fen(amount),
                    env=env,
                    reason='拼团未成团或付款未满足参团资格，全额退款',
                )
            else:
                await provider.notify_provide_goods(order_no=order_no, env=env)
                result = {'status': 'SUCCESS'}
        except Exception as exc:
            async with async_db_session.begin() as db:
                task = (
                    await db.scalars(select(PayGroupBuyTask).where(PayGroupBuyTask.id == task_id).with_for_update())
                ).one()
                if task.status != 'done' and task.attempts == attempt:
                    task.error = str(exc)[:512]
                    task.status = 'manual_review' if kind == 'refund' else 'pending'
                    task.available_at = timezone.now() + timedelta(minutes=1)
            return
        await GroupBuyWorker._save_outbound_result(task_id, kind, order_no, pay_type, refund_no, result)

    @staticmethod
    async def _save_outbound_result(
        task_id: int, kind: str, order_no: str, pay_type: str, refund_no: str, result: dict
    ) -> None:
        async with async_db_session.begin() as db:
            txn = await pay_transaction_dao.get_by_order_no(db, order_no, for_update=True)
            order = await pay_order_dao.get_by_order_no(db, order_no, for_update=True)
            task = (
                await db.scalars(select(PayGroupBuyTask).where(PayGroupBuyTask.id == task_id).with_for_update())
            ).one()
            if task.status == 'done':
                return
            if kind == 'refund':
                if pay_type == 'virtual' and result.get('errcode') == 0:
                    result = {**result, 'status': 'PROCESSING', 'refund_no': refund_no}
                if result.get('status') not in ('SUCCESS', 'PROCESSING'):
                    task.status, task.error = 'manual_review', '渠道退款结果不明确，请核实'
                    return
                task.payload = {
                    **task.payload,
                    'refund_accepted': True,
                    'channel_refund_no': str(result.get('refund_no') or refund_no),
                }
                if txn.status != 'refunded':
                    txn.refund_no = str(result.get('refund_no') or refund_no)
                    await pay_service._mark_refund_result(
                        db=db, txn_id=txn.id, data={'refund_status': result['status'], 'raw_data': result}
                    )
                # PROCESSING 不等于完成，依靠已持久化回调补偿任务最终撤销权益。
                task.status = 'done' if order.status == 'refunded' else 'manual_review'
                task.error = None if order.status == 'refunded' else '渠道已受理，等待退款确认'
            else:
                task.status = 'done'
            task.lease_until = None

    @staticmethod
    async def drain(limit: int = 100) -> dict:
        completed = 0
        for _ in range(limit):
            async with async_db_session.begin() as db:
                task = await group_buy_dao.claim(db)
                if not task:
                    break
                task_id, attempt = task.id, task.attempts
            try:
                await GroupBuyWorker.execute(task_id, attempt)
            except Exception as exc:
                log.exception(f'拼团任务执行失败: task_id={task_id}')
                async with async_db_session.begin() as db:
                    task = (
                        await db.scalars(select(PayGroupBuyTask).where(PayGroupBuyTask.id == task_id).with_for_update())
                    ).one()
                    if task.status == 'running' and task.attempts == attempt:
                        task.status = 'failed' if attempt >= 10 else 'pending'
                        task.error = str(exc)[:512]
                        task.available_at = timezone.now() + timedelta(seconds=min(3600, 15 * 2 ** min(attempt, 8)))
                        task.lease_until = None
            completed += 1
        return {'processed': completed}

    @staticmethod
    async def reconcile_due_teams(limit: int = 50) -> dict:
        now = timezone.now()
        async with async_db_session() as db:
            codes = list(
                (
                    await db.scalars(
                        select(PayGroupBuyTeam.share_code)
                        .where(
                            ((PayGroupBuyTeam.status == 'draft') & (PayGroupBuyTeam.draft_until <= now))
                            | ((PayGroupBuyTeam.status == 'forming') & (PayGroupBuyTeam.deadline <= now)),
                        )
                        .order_by(PayGroupBuyTeam.id)
                        .limit(limit)
                    )
                ).all()
            )
        closed = 0
        for code in codes:
            try:
                async with async_db_session() as db:
                    team = await group_buy_dao.team(db, code)
                    members = await group_buy_dao.members(db, team.id)
                    order_ids = [m.order_id for m in members if m.order_id]
                for order_id in order_ids:
                    await GroupBuyWorker._reconcile_order(order_id, code)
                async with async_db_session.begin() as db:
                    team = await group_buy_dao.team(db, code, lock=True)
                    if team.status not in ('draft', 'forming'):
                        continue
                    deadline = team.deadline or team.draft_until
                    if timezone.now() < deadline:
                        continue
                    team.status = 'cancelled' if team.status == 'draft' else 'expired'
                    # 只修改成员和创建退款任务，不在团锁中锁订单。
                    for member in await group_buy_dao.members(db, team.id):
                        if member.status == 'paid' and member.order_id:
                            member.status = 'refund_pending'
                            await group_buy_dao.enqueue(
                                db,
                                key=f'gb:refund:{(await db.get(PayOrder, member.order_id)).order_no}',
                                kind='refund',
                                team_id=team.id,
                                order_id=member.order_id,
                                payload={'refund_no': pay_service._generate_refund_no()},
                            )
                        elif member.status == 'reserved':
                            member.status = 'expired'
                    closed += 1
            except Exception:
                log.exception(f'拼团到期核实失败，等待补偿: share_code={code}')
        return {'closed': closed}

    @staticmethod
    async def _reconcile_order(order_id: int, code: str) -> None:
        async with async_db_session() as db:
            order = await db.get(PayOrder, order_id)
            txn = await pay_transaction_dao.get_by_order_no(db, order.order_no)
            if not txn or txn.status in ('refund_pending', 'refunded'):
                return
            order_no = order.order_no
            pay_type, env, openid = order.pay_type, order.extra_data.get('env', 0), order.extra_data.get('openid')
            paid = txn.status == 'paid'
        data = None
        if pay_type == 'virtual':
            data = await GroupBuyWorker._verify_virtual_order(order)
            paid = data.get('trade_state') == 'SUCCESS'
        elif not paid:
            provider = get_provider(pay_type)
            data = provider.normalize_query_data(
                await provider.query(order_no=order_no, env=env, openid=openid), order_no=order_no
            )
            if data.get('trade_state') not in ('SUCCESS', 'NOTPAY', 'CLOSED', 'REVOKED', 'PAYERROR'):
                raise errors.GatewayError(msg='到期查单结果未知，保留团等待核实')
            paid = data.get('trade_state') == 'SUCCESS'
        if not paid:
            return
        async with async_db_session.begin() as db:
            txn = await pay_transaction_dao.get_by_order_no(db, order_no, for_update=True)
            if data:
                pay_service._validate_channel_result(txn, data, provider)
                await pay_service._mark_payment_success(
                    db=db,
                    txn_id=txn.id,
                    order_no=order_no,
                    trade_no=data['trade_no'],
                    paid_time=pay_service._resolve_paid_time(data.get('paid_time')),
                    notify_data=data,
                )
            order = await pay_order_dao.get_by_order_no(db, order_no, for_update=True)
            preliminary_team = await group_buy_dao.team(db, code)
            await db.execute(
                select(PayGroupBuyActivity.id)
                .where(PayGroupBuyActivity.id == preliminary_team.activity_id)
                .with_for_update()
            )
            team = await group_buy_dao.team(db, code, lock=True)
            await GroupBuyWorker._payment(db, order, team)

    @staticmethod
    async def _verify_virtual_order(order: PayOrder) -> dict:
        provider = get_provider('virtual')
        env = int(order.extra_data.get('env') or 0)
        data = provider.normalize_query_data(
            await provider.query(order_no=order.order_no, env=env, openid=order.extra_data.get('openid')),
            order_no=order.order_no,
        )
        if data.get('trade_state') in ('NOTPAY', 'CLOSED'):
            if order.status == 'paid':
                raise errors.GatewayError(msg='虚拟支付付款通知与渠道查询不一致，等待核实')
            return data
        if data.get('trade_state') != 'SUCCESS':
            raise errors.GatewayError(msg='虚拟支付付款状态未知，等待核实')
        if (
            str(data.get('order_no')) != order.order_no
            or data.get('order_type') not in (0, 7)
            or data.get('env_type') != env + 1
            or data.get('total_fee') != pay_service._yuan_to_fen(order.amount)
            or not data.get('trade_no')
        ):
            raise errors.GatewayError(msg='虚拟支付订单金额、来源或环境不匹配')
        return data

    @staticmethod
    async def reconcile_refunds(limit: int = 50) -> dict:
        async with async_db_session() as db:
            rows = list(
                (
                    await db.scalars(
                        select(PayGroupBuyTask)
                        .where(PayGroupBuyTask.kind == 'refund', PayGroupBuyTask.status == 'manual_review')
                        .order_by(PayGroupBuyTask.id)
                        .limit(limit)
                    )
                ).all()
            )
        confirmed = 0
        for task in rows:
            try:
                async with async_db_session() as db:
                    order = await db.get(PayOrder, task.order_id)
                    txn = await pay_transaction_dao.get_by_order_no(db, order.order_no)
                    refund_no = txn.refund_no if txn else None
                if order.status == 'refunded':
                    async with async_db_session.begin() as db:
                        current = await pay_order_dao.get_by_order_no(db, order.order_no, for_update=True)
                        await GroupBuyWorker.refund_event(db, current)
                    continue
                query = getattr(get_provider(order.pay_type), 'query_refund', None)
                if not query or not refund_no:
                    continue
                result = await query(
                    order_no=order.order_no,
                    refund_no=refund_no,
                    openid=order.extra_data.get('openid'),
                    env=int(order.extra_data.get('env') or 0),
                )
                if result.get('refund_status') not in ('SUCCESS', 'FAILED'):
                    continue
                if result.get('refund_fee') != pay_service._yuan_to_fen(order.amount):
                    raise errors.GatewayError(msg='退款查证金额不匹配')
                async with async_db_session.begin() as db:
                    txn = await pay_transaction_dao.get_by_order_no(db, order.order_no, for_update=True)
                    await pay_service._mark_refund_result(db=db, txn_id=txn.id, data=result)
                    current_task = (
                        await db.scalars(select(PayGroupBuyTask).where(PayGroupBuyTask.id == task.id).with_for_update())
                    ).one()
                    if result['refund_status'] == 'FAILED':
                        current_task.error = '渠道确认退款失败，请人工核实后重试'
                        current_task.payload = {**current_task.payload, 'channel_failed': True}
                    else:
                        confirmed += 1
            except Exception:
                log.exception(f'拼团退款查证失败，保留任务等待补偿: task_id={task.id}')
        return {'refunds_confirmed': confirmed}


group_buy_worker = GroupBuyWorker()
