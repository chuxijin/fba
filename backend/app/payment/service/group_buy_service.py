#!/usr/bin/env python3
import secrets

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CommonStatus
from backend.app.access.crud.crud_template import subscription_template_dao
from backend.app.access.model.template import SubscriptionTemplate
from backend.app.access.service.sale_snapshot_service import sale_snapshot_service
from backend.app.payment.crud.crud_group_buy import group_buy_dao
from backend.app.payment.crud.crud_pay_order import pay_order_dao
from backend.app.payment.crud.crud_pay_transaction import pay_transaction_dao
from backend.app.payment.model.group_buy import (
    PayGroupBuyActivity,
    PayGroupBuyMember,
    PayGroupBuyTask,
    PayGroupBuyTeam,
    PayGroupBuyTier,
)
from backend.app.payment.model.pay_order import PayOrder
from backend.app.payment.schema.group_buy import (
    GroupBuyActivityParam,
    GroupBuyCreateTeamParam,
    GroupBuyPrepayParam,
    GroupBuySummary,
)
from backend.app.payment.schema.pay import CreatePrepayParam, SubscriptionPrepayResult
from backend.app.payment.service.pay_order_service import pay_order_service
from backend.app.payment.service.pay_service import pay_service
from backend.common.exception import errors
from backend.common.payment import get_provider
from backend.core.conf import settings
from backend.utils.timezone import timezone

OPEN_TEAM_AVATAR_LIMIT = 3


class GroupBuyService:
    @staticmethod
    def ensure_open() -> None:
        if not settings.PAYMENT_GROUP_BUY_ENABLE:
            raise errors.ForbiddenError(msg='拼团暂未开放')

    @staticmethod
    async def configure(
        db: AsyncSession, *, obj: GroupBuyActivityParam, user_id: int, activity_id: int | None = None
    ) -> int:
        if (
            any(channel not in settings.PAYMENT_GROUP_BUY_CHANNELS for channel in obj.channels)
            and obj.status == 'active'
        ):
            raise errors.RequestError(msg='活动渠道尚未通过拼团验收，不能启用')
        template = await subscription_template_dao.get_by_code(db, obj.template_code)
        if not template or template.code.startswith('GBS_') or template.status != CommonStatus.ACTIVE:
            raise errors.RequestError(msg='请选择有效的原始订阅套餐')
        await GroupBuyService._validate_rewards(db, obj, template)
        activity = None
        if activity_id is not None:
            activity = (
                await db.scalars(
                    select(PayGroupBuyActivity).where(PayGroupBuyActivity.id == activity_id).with_for_update()
                )
            ).one_or_none()
            if not activity:
                raise errors.NotFoundError(msg='拼团活动不存在')
        rules = obj.model_dump(
            mode='json', exclude={'tiers', 'name', 'template_code', 'description', 'status', 'starts_at', 'ends_at'}
        )
        if activity is None:
            activity = PayGroupBuyActivity(
                name=obj.name,
                template_code=obj.template_code,
                starts_at=obj.starts_at,
                ends_at=obj.ends_at,
                rules=rules,
                status=obj.status,
                description=obj.description,
                created_by=user_id,
            )
            db.add(activity)
            await db.flush()
        else:
            activity.name, activity.template_code = obj.name, obj.template_code
            activity.starts_at, activity.ends_at = obj.starts_at, obj.ends_at
            activity.rules, activity.status, activity.description = rules, obj.status, obj.description
            activity.revision += 1
            activity.updated_by = user_id
            from sqlalchemy import delete

            await db.execute(delete(PayGroupBuyTier).where(PayGroupBuyTier.activity_id == activity.id))
        for tier in obj.tiers:
            db.add(
                PayGroupBuyTier(
                    activity_id=activity.id,
                    people=tier.people,
                    price_cents=tier.price_cents,
                    rewards=tier.model_dump(mode='json', exclude={'people', 'price_cents'}),
                )
            )
        await db.flush()
        return activity.id

    @staticmethod
    async def _validate_rewards(db: AsyncSession, obj: GroupBuyActivityParam, template: SubscriptionTemplate) -> None:
        for tier in obj.tiers:
            if tier.price_cents >= int(template.price_cents or 0):
                raise errors.RequestError(msg='团价必须低于套餐原价')
            for reward in [*tier.member_rewards, *tier.leader_rewards]:
                source = await subscription_template_dao.get_by_code(db, reward.template_code)
                if not source or source.status != CommonStatus.ACTIVE or source.code.startswith('GBS_'):
                    raise errors.RequestError(msg='奖励套餐不存在或未启用')
                await sale_snapshot_service.capture(db, source, duration_days=reward.duration_days)
        await sale_snapshot_service.capture(db, template)

    @staticmethod
    async def activities(db: AsyncSession, *, admin: bool = False) -> list[dict]:
        stmt = select(PayGroupBuyActivity).order_by(PayGroupBuyActivity.id.desc()).limit(100)
        if not admin:
            if not settings.PAYMENT_GROUP_BUY_ENABLE:
                return []
            now = timezone.now()
            stmt = stmt.where(
                PayGroupBuyActivity.status == 'active',
                PayGroupBuyActivity.starts_at <= now,
                PayGroupBuyActivity.ends_at > now,
            )
        result = []
        for activity in (await db.scalars(stmt)).all():
            tiers = (
                await db.scalars(
                    select(PayGroupBuyTier)
                    .where(PayGroupBuyTier.activity_id == activity.id)
                    .order_by(PayGroupBuyTier.people)
                )
            ).all()
            result.append({
                'id': activity.id,
                'name': activity.name,
                'description': activity.description,
                'template_code': activity.template_code,
                'starts_at': activity.starts_at,
                'ends_at': activity.ends_at,
                'status': activity.status,
                'revision': activity.revision,
                **activity.rules,
                'tiers': [{'people': t.people, 'price_cents': t.price_cents, **t.rewards} for t in tiers],
            })
        return result

    @staticmethod
    async def open_teams(db: AsyncSession, *, limit: int = 20) -> list[dict]:
        """在售活动中可参与的进行中团；只下发展示字段与已付款成员头像，不含账号与订单。"""
        if not settings.PAYMENT_GROUP_BUY_ENABLE:
            return []
        now = timezone.now()
        teams = await group_buy_dao.open_teams(db, now=now, limit=limit)
        if not teams:
            return []
        members = await group_buy_dao.paid_members(db, [team.id for team in teams])
        avatars = await group_buy_dao.avatars(db, list({member.user_id for member in members}))
        grouped: dict[int, list[PayGroupBuyMember]] = {}
        for member in members:
            grouped.setdefault(member.team_id, []).append(member)
        result = []
        for team in teams:
            paid = grouped.get(team.id, [])
            urls = [avatars[member.user_id] for member in paid if avatars.get(member.user_id)]
            result.append({
                'activity_id': team.activity_id,
                'template_code': team.snapshot.get('template_code', ''),
                'template_name': team.snapshot.get('base', {}).get('name', ''),
                'share_code': team.share_code,
                'people': team.people,
                'paid_people': len(paid),
                'remaining_people': max(0, team.people - len(paid)),
                'price_cents': team.snapshot.get('price_cents', 0),
                'deadline': team.deadline,
                'avatars': urls[:OPEN_TEAM_AVATAR_LIMIT],
            })
        return result

    @staticmethod
    async def _check_participation(
        db: AsyncSession, activity_id: int, user_id: int, limit: int, *, excluding_member: int | None = None
    ) -> None:
        stmt = (
            select(func.count())
            .select_from(PayGroupBuyMember)
            .where(
                PayGroupBuyMember.activity_id == activity_id,
                PayGroupBuyMember.user_id == user_id,
                (PayGroupBuyMember.status.in_(['paid', 'refund_pending']))
                | ((PayGroupBuyMember.status == 'reserved') & (PayGroupBuyMember.reserved_until > timezone.now())),
            )
        )
        if excluding_member:
            stmt = stmt.where(PayGroupBuyMember.id != excluding_member)
        if int((await db.scalar(stmt)) or 0) >= limit:
            raise errors.ForbiddenError(msg='已达到该活动的参与次数限制')

    @staticmethod
    async def create_team(db: AsyncSession, *, user_id: int, obj: GroupBuyCreateTeamParam) -> PayGroupBuyTeam:
        GroupBuyService.ensure_open()
        activity = (
            await db.scalars(
                select(PayGroupBuyActivity).where(PayGroupBuyActivity.id == obj.activity_id).with_for_update()
            )
        ).one_or_none()
        if not activity:
            raise errors.NotFoundError(msg='拼团活动不存在')
        # 活动锁统一串行化报名资格，开团请求也可安全重试。
        existing = (
            await db.scalars(
                select(PayGroupBuyTeam).where(
                    PayGroupBuyTeam.leader_user_id == user_id, PayGroupBuyTeam.request_key == obj.request_key
                )
            )
        ).one_or_none()
        if existing:
            if existing.activity_id != obj.activity_id or existing.people != obj.people:
                raise errors.ConflictError(msg='同一开团请求不能更改活动或人数')
            return existing
        now = timezone.now()
        if activity.status != 'active' or not activity.starts_at <= now < activity.ends_at:
            raise errors.ForbiddenError(msg='活动当前不可开团')
        await GroupBuyService._check_participation(
            db, activity.id, user_id, activity.rules['max_participations_per_user']
        )
        tier = (
            await db.scalars(
                select(PayGroupBuyTier).where(
                    PayGroupBuyTier.activity_id == activity.id, PayGroupBuyTier.people == obj.people
                )
            )
        ).one_or_none()
        if not tier:
            raise errors.RequestError(msg='活动没有开放该人数档位')
        template = await subscription_template_dao.get_by_code(db, activity.template_code)
        if not template:
            raise errors.NotFoundError(msg='套餐不存在')
        pay_order_service._ensure_template_saleable(template)
        if tier.price_cents >= int(template.price_cents):
            raise errors.RequestError(msg='活动团价已不低于原价，请重新配置活动')
        snapshot = {
            'revision': activity.revision,
            'name': activity.name,
            'activity_end': activity.ends_at.isoformat(),
            'template_code': template.code,
            'price_cents': tier.price_cents,
            'original_price_cents': template.price_cents,
            'base': await sale_snapshot_service.capture(db, template),
            **activity.rules,
            'rewards': {},
            'virtual_product_id': tier.rewards.get('virtual_product_id'),
        }
        snapshot['rewards'] = await GroupBuyService._capture_rewards(db, tier)
        team = PayGroupBuyTeam(
            activity_id=activity.id,
            leader_user_id=user_id,
            share_code=secrets.token_hex(12),
            request_key=obj.request_key,
            people=obj.people,
            snapshot=snapshot,
            draft_until=min(now + timedelta(seconds=activity.rules['reservation_seconds']), activity.ends_at),
            created_by=user_id,
        )
        db.add(team)
        await db.flush()
        db.add(
            PayGroupBuyMember(
                team_id=team.id, activity_id=activity.id, user_id=user_id, reserved_until=team.draft_until
            )
        )
        await db.flush()
        return team

    @staticmethod
    async def _capture_rewards(db: AsyncSession, tier: PayGroupBuyTier) -> dict:
        rewards = {}
        for role in ('member_rewards', 'leader_rewards'):
            rewards[role] = []
            for reward in tier.rewards[role]:
                source = await subscription_template_dao.get_by_code(db, reward['template_code'])
                if not source or source.status != CommonStatus.ACTIVE:
                    raise errors.RequestError(msg='活动奖励套餐已失效')
                rewards[role].append(
                    await sale_snapshot_service.capture(db, source, duration_days=reward['duration_days'])
                )
        return rewards

    @staticmethod
    async def reserve_order(db: AsyncSession, *, code: str, user_id: int, obj: GroupBuyPrepayParam) -> PayOrder:
        GroupBuyService.ensure_open()
        if getattr(settings, 'VIRTUAL_PAY_ENV', None) == 0:
            obj.env = 0
        elif settings.ENVIRONMENT == 'prod' and obj.env != 0:
            raise errors.ForbiddenError(msg='生产拼团只允许现网付款')
        team = await group_buy_dao.team(db, code)
        if not team:
            raise errors.NotFoundError(msg='拼团不存在')
        # 报名锁序为活动 -> 团；付款任务为交易 -> 订单 -> 活动 -> 团。
        await db.execute(
            select(PayGroupBuyActivity.id).where(PayGroupBuyActivity.id == team.activity_id).with_for_update()
        )
        team = await group_buy_dao.team(db, code, lock=True)
        now = timezone.now()
        if team.status not in ('draft', 'forming') or (team.status == 'draft' and team.leader_user_id != user_id):
            raise errors.ForbiddenError(msg='当前不可参与该团')
        deadline = team.deadline if team.status == 'forming' else team.draft_until
        if deadline is None or now >= deadline:
            raise errors.ForbiddenError(msg='该团已到期')
        if obj.pay_type not in team.snapshot['channels'] or obj.pay_type not in settings.PAYMENT_GROUP_BUY_CHANNELS:
            raise errors.ForbiddenError(msg='该支付渠道暂不支持拼团')
        members = await group_buy_dao.members(db, team.id)
        member = next((m for m in members if m.user_id == user_id), None)
        existing = await GroupBuyService._existing_order(db, member, obj, now)
        if existing:
            return existing
        occupied = sum(
            m.status == 'paid' or (m.status == 'reserved' and m.reserved_until > now) for m in members if m != member
        )
        if occupied >= team.people:
            raise errors.ForbiddenError(msg='该团名额已被占用')
        await GroupBuyService._check_participation(
            db,
            team.activity_id,
            user_id,
            team.snapshot['max_participations_per_user'],
            excluding_member=member.id if member else None,
        )
        if obj.inviter_user_id is not None and not any(
            m.user_id == obj.inviter_user_id and m.status == 'paid' for m in members
        ):
            raise errors.RequestError(msg='拼团邀请人必须是该团已付款成员')
        if member is None:
            member = PayGroupBuyMember(
                team_id=team.id, activity_id=team.activity_id, user_id=user_id, reserved_until=deadline
            )
            db.add(member)
        member.status = 'reserved'
        member.reserved_until = min(deadline, now + timedelta(seconds=team.snapshot['reservation_seconds']))
        member.inviter_user_id = obj.inviter_user_id
        await db.flush()
        order = await pay_order_dao.create_from_dict(
            db,
            {
                'order_no': pay_order_service._generate_order_no(),
                'user_id': user_id,
                'biz_type': 'subscription_template',
                'item_code': team.snapshot['template_code'],
                'item_name': team.snapshot['base']['name'],
                'amount': Decimal(team.snapshot['price_cents']) / Decimal(100),
                'pay_type': obj.pay_type,
                'purchase_mode': 'group_buy',
                'created_by': user_id,
                'extra_data': {
                    'group_buy_team_id': team.id,
                    'group_buy_share_code': team.share_code,
                    'group_buy_member_id': member.id,
                    'group_buy_reserved_until': member.reserved_until.isoformat(),
                    'group_buy_base': team.snapshot['base'],
                    'env': obj.env,
                },
            },
        )
        order.extra_data = {**order.extra_data, 'virtual_product_id': team.snapshot.get('virtual_product_id')}
        member.order_id = order.id
        await db.flush()
        return order

    @staticmethod
    async def _existing_order(
        db: AsyncSession, member: PayGroupBuyMember | None, obj: GroupBuyPrepayParam, now: datetime
    ) -> PayOrder | None:
        if not member:
            return None
        if member.status in ('paid', 'refund_pending'):
            raise errors.ForbiddenError(msg='已有付款或退款处理中，请查看订单状态')
        if member.order_id and member.status == 'reserved' and member.reserved_until > now:
            order = await db.get(PayOrder, member.order_id)
            if (
                order
                and order.status == 'pending'
                and order.pay_type == obj.pay_type
                and (order.extra_data or {}).get('env', 0) == obj.env
            ):
                return order
            raise errors.ForbiddenError(msg='已有订单，请刷新订单状态或等待占位到期')
        return None

    @staticmethod
    async def prepay(*, order_id: int, user_id: int, obj: GroupBuyPrepayParam) -> SubscriptionPrepayResult:
        from backend.database.db import async_db_session

        # 微信换会话在业务锁之外完成，不改变渠道售卖快照。
        openid = session_key = None
        if obj.pay_type == 'virtual':
            async with async_db_session() as db:
                openid, session_key = await pay_order_service._resolve_miniapp_session(
                    db, user_id=user_id, wx_code=obj.wx_code
                )
        async with async_db_session.begin() as db:
            order = (
                await db.scalars(
                    select(PayOrder)
                    .where(PayOrder.id == order_id)
                    .with_for_update(key_share=True)
                    .execution_options(populate_existing=True)
                )
            ).one()
            result_or_params = await GroupBuyService._prepare_prepay(
                db, order, user_id=user_id, openid=openid, session_key=session_key
            )
        if isinstance(result_or_params, SubscriptionPrepayResult):
            return result_or_params
        params = result_or_params
        # 意图、订单与支付交易已提交。超时不回滚真实购买凭证，也不盲目重新向渠道下单。
        provider = get_provider(params.pay_type)
        try:
            result = await provider.prepay(
                order_no=params.order_no,
                total_fee=pay_service._yuan_to_fen(params.amount),
                description=params.product_name,
                pay_type=params.pay_type,
                openid=openid,
                session_key=session_key,
                product_id=params.product_id,
                env=params.env,
            )
        except Exception:
            async with async_db_session.begin() as db:
                order = (await db.scalars(select(PayOrder).where(PayOrder.id == order_id).with_for_update())).one()
                order.extra_data = {**order.extra_data, 'group_buy_prepay_state': 'unknown'}
            raise
        async with async_db_session.begin() as db:
            order = (await db.scalars(select(PayOrder).where(PayOrder.id == order_id).with_for_update())).one()
            order.extra_data = {**order.extra_data, 'group_buy_pay_params': result, 'group_buy_prepay_state': 'ready'}
            return SubscriptionPrepayResult(
                order_no=order.order_no, transaction_no=order.transaction_no, pay_params=result
            )

    @staticmethod
    async def _prepare_prepay(
        db: AsyncSession, order: PayOrder, *, user_id: int, openid: str | None, session_key: str | None
    ) -> SubscriptionPrepayResult | CreatePrepayParam:
        if order.user_id != user_id or order.status != 'pending':
            raise errors.ForbiddenError(msg='该订单当前不能付款')
        extra = dict(order.extra_data or {})
        if timezone.now() >= datetime.fromisoformat(extra['group_buy_reserved_until']):
            raise errors.ForbiddenError(msg='占位已到期，请重新参与')
        if extra.get('group_buy_pay_params'):
            params = dict(extra['group_buy_pay_params'])
            if order.pay_type == 'virtual' and session_key:
                params['signature'] = get_provider('virtual')._calc_signature(params['signData'], session_key)
                order.extra_data = {**extra, 'group_buy_pay_params': params, 'openid': openid}
            return SubscriptionPrepayResult(
                order_no=order.order_no, transaction_no=order.transaction_no, pay_params=params
            )
        if extra.get('group_buy_prepay_state') in ('dispatching', 'unknown'):
            raise errors.ConflictError(msg='预下单结果正在核实，请刷新订单状态或等待占位到期')
        transaction_no = pay_service._generate_transaction_no()
        await pay_transaction_dao.create_from_dict(
            db,
            {
                'transaction_no': transaction_no,
                'order_no': order.order_no,
                'biz_type': order.biz_type,
                'user_id': user_id,
                'pay_type': order.pay_type,
                'amount': order.amount,
                'status': 'pending',
                'product_name': order.item_name,
                'created_by': user_id,
            },
        )
        params = CreatePrepayParam(
            order_no=order.order_no,
            biz_type=order.biz_type,
            pay_type=order.pay_type,
            amount=order.amount,
            product_name=order.item_name,
            user_id=user_id,
            openid=openid,
            session_key=session_key,
            product_id=extra.get('virtual_product_id'),
            env=extra['env'],
        )
        order.transaction_no = transaction_no
        order.extra_data = {**extra, 'openid': openid, 'group_buy_prepay_state': 'dispatching'}
        await db.flush()
        return params

    @staticmethod
    async def summary(db: AsyncSession, order: PayOrder) -> GroupBuySummary | None:
        if getattr(order, 'purchase_mode', 'direct') != 'group_buy':
            return None
        team = await db.get(PayGroupBuyTeam, (order.extra_data or {}).get('group_buy_team_id'))
        if not team:
            return None
        members = await group_buy_dao.members(db, team.id)
        tasks = list(
            (
                await db.scalars(
                    select(PayGroupBuyTask).where(
                        PayGroupBuyTask.order_id == order.id, PayGroupBuyTask.kind == 'reward'
                    )
                )
            ).all()
        )
        reward = 'pending'
        if tasks and all(t.status == 'done' for t in tasks):
            reward = 'granted'
        elif any(t.status in ('failed', 'manual_review') for t in tasks):
            reward = 'failed'
        return GroupBuySummary(
            share_code=team.share_code,
            status=team.status,
            people=team.people,
            paid_people=sum(m.status == 'paid' for m in members),
            deadline=team.deadline or team.draft_until,
            base_status=order.fulfill_status,
            reward_status=reward,
        )

    @staticmethod
    async def detail(db: AsyncSession, code: str, *, user_id: int | None = None) -> dict:
        team = await group_buy_dao.team(db, code)
        if not team:
            raise errors.NotFoundError(msg='拼团不存在')
        members = await group_buy_dao.members(db, team.id)
        own = next((m for m in members if m.user_id == user_id), None)
        order = await db.get(PayOrder, own.order_id) if own and own.order_id else None
        avatars = await group_buy_dao.avatars(db, [m.user_id for m in members])
        return {
            'share_code': team.share_code,
            'activity_id': team.activity_id,
            'name': team.snapshot['name'],
            'status': team.status,
            'people': team.people,
            'paid_people': sum(m.status == 'paid' for m in members),
            'price_cents': team.snapshot['price_cents'],
            'original_price_cents': team.snapshot['original_price_cents'],
            'template_name': team.snapshot['base']['name'],
            'deadline': team.deadline or team.draft_until,
            'server_time': timezone.now(),
            'rewards': {
                k: [{'name': r['name'], 'duration_days': r['duration_days']} for r in v]
                for k, v in team.snapshot['rewards'].items()
            },
            'members': [
                {
                    'label': f'成员 {i + 1}',
                    'avatar': avatars.get(m.user_id),
                    'is_leader': m.user_id == team.leader_user_id,
                    'status': m.status,
                    'is_me': m.user_id == user_id,
                }
                for i, m in enumerate(members)
                if m.status == 'paid' or m == own
            ],
            'channels': team.snapshot['channels'],
            'is_leader': user_id == team.leader_user_id,
            'my_order': {
                'order_no': order.order_no,
                'status': order.status,
                'pay_type': order.pay_type,
                'reserved_until': (order.extra_data or {}).get('group_buy_reserved_until'),
                'fulfill_status': order.fulfill_status,
                'group_buy': (await GroupBuyService.summary(db, order)).model_dump(),
            }
            if order
            else None,
        }


group_buy_service = GroupBuyService()
