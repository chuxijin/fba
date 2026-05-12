#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy import Select, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model import user_role
from backend.app.admin.service.user_role_expiry_service import user_role_expiry_service
from backend.app.admin.utils.cache import user_cache_manager
from backend.app.membership.crud.crud_membership import user_membership_dao
from backend.app.membership.crud.crud_plan import membership_plan_dao
from backend.app.membership.crud.crud_record import membership_record_dao
from backend.app.membership.crud.crud_tier import membership_tier_dao
from backend.app.membership.model.membership import UserMembership
from backend.app.membership.model.plan import MembershipPlan
from backend.app.membership.model.record import MembershipRecord
from backend.app.membership.model.tier import MembershipTier
from backend.app.membership.schema.membership import OpenMembershipParam
from backend.app.question_bank.crud.crud_user_message import user_message_dao
from backend.app.question_bank.schema.user_message import CreateUserMessageParam
from backend.common.exception import errors
from backend.common.log import log
from backend.database.db import async_db_session
from backend.utils.timezone import timezone


class MembershipService:
    """会员服务"""

    MEMBERSHIP_CENTER_LINK = '/pkg/mine/membership-center'

    @staticmethod
    async def _ensure_user_role(db: AsyncSession, *, user_id: int, role_id: int) -> None:
        """
        确保用户角色关联存在

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param role_id: 角色 ID
        :return:
        """
        stmt = select(user_role).where(
            user_role.c.user_id == user_id,
            user_role.c.role_id == role_id,
        )
        result = await db.execute(stmt)
        if not result.first():
            await db.execute(insert(user_role).values(user_id=user_id, role_id=role_id))

    @staticmethod
    async def _get_plan_and_tier(db: AsyncSession, *, plan_id: int) -> tuple[MembershipPlan, MembershipTier]:
        """
        获取有效的会员计划与会员等级

        :param db: 数据库会话
        :param plan_id: 计划 ID
        :return:
        """
        plan = await membership_plan_dao.select_model(db, plan_id)
        if not plan:
            raise errors.NotFoundError(msg='会员计划不存在')
        if plan.status != 1:
            raise errors.RequestError(msg='会员计划已下架')

        tier = await membership_tier_dao.select_model(db, plan.tier_id)
        if not tier:
            raise errors.NotFoundError(msg='会员等级不存在')
        if tier.status != 1:
            raise errors.RequestError(msg='会员等级已停用')

        return plan, tier

    @staticmethod
    async def grant_by_plan(
        db: AsyncSession,
        *,
        user_id: int,
        plan_id: int,
        source: str,
        source_key: str,
        op_type: str,
        days: int | None = None,
        source_detail: str | None = None,
        remark: str | None = None,
    ) -> UserMembership:
        """
        基于计划发放会员时长

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param plan_id: 计划 ID
        :param source: 来源
        :param source_key: 来源幂等键
        :param op_type: 操作类型
        :param days: 发放天数
        :param source_detail: 来源详情
        :param remark: 备注
        :return:
        """
        if not source_key:
            raise errors.RequestError(msg='source_key 不能为空')

        plan, tier = await MembershipService._get_plan_and_tier(db, plan_id=plan_id)
        grant_days = int(days if days is not None else plan.duration_days)
        if grant_days <= 0:
            raise errors.RequestError(msg='发放天数必须大于 0')

        existing_record = await membership_record_dao.get_by_idempotency(
            db,
            user_id=user_id,
            family_code=tier.family_code,
            source=source,
            source_key=source_key,
            op_type=op_type,
        )
        if existing_record:
            membership = await user_membership_dao.get_by_user_and_family(db, user_id, tier.family_code)
            if not membership:
                raise errors.RequestError(msg='幂等流水存在但会员状态缺失，请人工处理')
            return membership

        now = timezone.now()
        membership = await user_membership_dao.get_by_user_and_family(
            db,
            user_id,
            tier.family_code,
            for_update=True,
        )

        valid_to_before = membership.valid_to if membership else None
        was_active = bool(
            membership
            and membership.status == 1
            and membership.valid_to
            and membership.valid_to > now
        )
        base_time = membership.valid_to if was_active and membership and membership.valid_to else now
        valid_to = base_time + timedelta(days=grant_days)
        effective_tier = tier
        if membership and membership.tier_weight > tier.weight:
            keep_tier = await membership_tier_dao.select_model(db, membership.tier_id)
            if keep_tier:
                effective_tier = keep_tier

        if membership:
            await user_membership_dao.update_model(
                db,
                membership.id,
                {
                    'family_code': effective_tier.family_code,
                    'tier_id': effective_tier.id,
                    'tier_code': effective_tier.code,
                    'tier_name': effective_tier.name,
                    'tier_grade': effective_tier.grade,
                    'tier_weight': effective_tier.weight,
                    'valid_from': membership.valid_from or now,
                    'valid_to': valid_to,
                    'source': source,
                    'source_key': source_key,
                    'status': 1,
                    'remark': remark,
                },
            )
            membership.family_code = effective_tier.family_code
            membership.tier_id = effective_tier.id
            membership.tier_code = effective_tier.code
            membership.tier_name = effective_tier.name
            membership.tier_grade = effective_tier.grade
            membership.tier_weight = effective_tier.weight
            membership.valid_from = membership.valid_from or now
            membership.valid_to = valid_to
            membership.source = source
            membership.source_key = source_key
            membership.status = 1
            membership.remark = remark
        else:
            membership = UserMembership(
                user_id=user_id,
                family_code=tier.family_code,
                tier_id=tier.id,
                tier_code=tier.code,
                tier_name=tier.name,
                tier_grade=tier.grade,
                tier_weight=tier.weight,
                exp=0,
                valid_from=now,
                valid_to=valid_to,
                source=source,
                source_key=source_key,
                status=1,
                remark=remark,
            )
            db.add(membership)
            await db.flush()

        record = MembershipRecord(
            user_id=user_id,
            family_code=tier.family_code,
            tier_id=membership.tier_id,
            plan_id=plan.id,
            op_type=op_type,
            days=grant_days,
            exp_delta=0,
            source=source,
            source_key=source_key,
            source_detail=source_detail,
            valid_to_before=valid_to_before,
            valid_to_after=valid_to,
            remark=remark,
        )
        db.add(record)

        try:
            await db.flush()
        except IntegrityError as exc:
            raise errors.RequestError(msg='source_key 已使用，拒绝重复发放') from exc

        await MembershipService._ensure_user_role(db, user_id=user_id, role_id=plan.role_id)
        if was_active:
            await user_role_expiry_service.extend_expiry(
                db,
                user_id=user_id,
                role_id=plan.role_id,
                extra_days=grant_days,
            )
        else:
            await user_role_expiry_service.assign_with_expiry(
                db,
                user_id=user_id,
                role_id=plan.role_id,
                duration_days=grant_days,
            )

        await user_cache_manager.clear([user_id])
        log.info(
            f'membership grant success: user_id={user_id}, tier={membership.tier_code}, '
            f'plan_id={plan.id}, days={grant_days}, source={source}, source_key={source_key}'
        )

        if op_type in ('open', 'add_days'):
            await MembershipService._send_grant_notification(
                db,
                user_id=user_id,
                tier=membership.tier_code,
                tier_name=membership.tier_name,
                plan=plan,
                op_type=op_type,
                days=grant_days,
                valid_to=valid_to,
                source=source,
                source_key=source_key,
            )

        return membership

    @staticmethod
    async def open_membership(db: AsyncSession, *, obj: OpenMembershipParam) -> UserMembership:
        """
        开通会员

        :param db: 数据库会话
        :param obj: 开通参数
        :return:
        """
        return await MembershipService.grant_by_plan(
            db,
            user_id=obj.user_id,
            plan_id=obj.plan_id,
            source=obj.source,
            source_key=obj.source_key,
            op_type='open',
            days=None,
            source_detail=None,
            remark=obj.remark,
        )

    @staticmethod
    async def add_days(
        db: AsyncSession,
        *,
        user_id: int,
        plan_id: int,
        days: int,
        source: str,
        source_key: str,
        source_detail: str | None = None,
        remark: str | None = None,
    ) -> UserMembership:
        """
        增加会员天数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param plan_id: 计划 ID
        :param days: 天数
        :param source: 来源
        :param source_key: 来源幂等键
        :param source_detail: 来源详情
        :param remark: 备注
        :return:
        """
        return await MembershipService.grant_by_plan(
            db,
            user_id=user_id,
            plan_id=plan_id,
            source=source,
            source_key=source_key,
            op_type='add_days',
            days=days,
            source_detail=source_detail,
            remark=remark,
        )

    @staticmethod
    async def _send_grant_notification(
        db: AsyncSession,
        *,
        user_id: int,
        tier: str,
        tier_name: str,
        plan: MembershipPlan,
        op_type: str,
        days: int,
        valid_to,
        source: str,
        source_key: str,
    ) -> None:
        """
        在会员发放成功后投递个人消息，失败仅记录日志不影响主流程

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param tier: 等级编码
        :param tier_name: 等级名称
        :param plan: 会员计划
        :param op_type: 操作类型(open/add_days)
        :param days: 本次发放天数
        :param valid_to: 新的到期时间
        :param source: 来源
        :param source_key: 来源幂等键
        :return:
        """
        valid_to_display = valid_to.strftime('%Y-%m-%d') if valid_to else '永久'
        if op_type == 'open':
            title = '会员开通成功'
            content = f'您的「{tier_name}」会员已开通，有效期至 {valid_to_display}'
        else:
            title = '会员时长已增加'
            content = f'您的「{tier_name}」会员已增加 {days} 天，有效期至 {valid_to_display}'

        message_param = CreateUserMessageParam(
            target_type='user',
            user_id=user_id,
            title=title,
            content=content,
            message_type='system',
            link_url=MembershipService.MEMBERSHIP_CENTER_LINK,
            payload={
                'event': op_type,
                'plan_id': plan.id,
                'plan_name': plan.name,
                'tier_code': tier,
                'tier_name': tier_name,
                'days': days,
                'valid_to': valid_to.isoformat() if valid_to else None,
                'source': source,
                'source_key': source_key,
            },
            publish_time=timezone.now(),
        )

        try:
            async with db.begin_nested():
                await user_message_dao.create(db, message_param)
        except Exception as exc:
            log.warning(
                f'membership notification failed (ignored): '
                f'user_id={user_id}, op_type={op_type}, source_key={source_key}, error={exc}'
            )

    @staticmethod
    async def revoke_by_source_key(
        db: AsyncSession,
        *,
        user_id: int,
        source: str,
        original_source_key: str,
        revoke_source_key: str,
        source_detail: str | None = None,
        remark: str | None = None,
    ) -> UserMembership | None:
        """
        按原发放幂等键反向回收会员时长

        定位原 grant 流水的 valid_to_after - valid_to_before 增量，
        将该增量从当前 valid_to 回退；回退后若 valid_to <= now 且当前状态为生效则标记过期，
        同时写一条 op_type='revoke' 流水并对称扣减用户角色有效期；
        其它来源的会员时长不受影响

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param source: 来源
        :param original_source_key: 原始发放幂等键
        :param revoke_source_key: 回收流水使用的幂等键
        :param source_detail: 来源详情
        :param remark: 备注
        :return:
        """
        grant_record = await membership_record_dao.get_grant_by_source_key(
            db,
            user_id=user_id,
            source=source,
            source_key=original_source_key,
        )
        if not grant_record:
            log.warning(
                f'membership revoke skipped (no grant record): '
                f'user_id={user_id}, source={source}, source_key={original_source_key}'
            )
            return None

        if not grant_record.valid_to_before or not grant_record.valid_to_after:
            log.warning(
                f'membership revoke skipped (grant record missing valid_to snapshots): '
                f'record_id={grant_record.id}'
            )
            return None

        delta = grant_record.valid_to_after - grant_record.valid_to_before
        delta_days = delta.days
        if delta_days <= 0:
            log.warning(
                f'membership revoke skipped (non-positive delta_days={delta_days}): '
                f'record_id={grant_record.id}'
            )
            return None

        tier = await membership_tier_dao.select_model(db, grant_record.tier_id)
        if not tier:
            log.warning(f'membership revoke skipped (tier not found): tier_id={grant_record.tier_id}')
            return None

        membership = await user_membership_dao.get_by_user_and_family(
            db,
            user_id,
            tier.family_code,
            for_update=True,
        )
        if not membership:
            log.warning(
                f'membership revoke skipped (membership row missing): '
                f'user_id={user_id}, family_code={tier.family_code}'
            )
            return None

        now = timezone.now()
        valid_to_before = membership.valid_to
        new_valid_to = valid_to_before - delta if valid_to_before else None
        if (
            new_valid_to is not None
            and membership.valid_from is not None
            and new_valid_to < membership.valid_from
        ):
            new_valid_to = membership.valid_from

        new_status = membership.status
        if new_status == 1 and new_valid_to is not None and new_valid_to <= now:
            new_status = 2

        await user_membership_dao.update_model(
            db,
            membership.id,
            {
                'valid_to': new_valid_to,
                'status': new_status,
            },
        )
        membership.valid_to = new_valid_to
        membership.status = new_status

        revoke_record = MembershipRecord(
            user_id=user_id,
            family_code=tier.family_code,
            tier_id=membership.tier_id,
            plan_id=grant_record.plan_id,
            op_type='revoke',
            days=-delta_days,
            exp_delta=0,
            source=source,
            source_key=revoke_source_key,
            source_detail=source_detail,
            valid_to_before=valid_to_before,
            valid_to_after=new_valid_to,
            remark=remark,
        )
        db.add(revoke_record)

        try:
            await db.flush()
        except IntegrityError as exc:
            raise errors.RequestError(msg='revoke_source_key 已使用，拒绝重复回收') from exc

        if grant_record.plan_id is not None:
            plan = await membership_plan_dao.select_model(db, grant_record.plan_id)
            if plan:
                await user_role_expiry_service.reduce_expiry(
                    db,
                    user_id=user_id,
                    role_id=plan.role_id,
                    reduce_days=delta_days,
                )

        await user_cache_manager.clear([user_id])
        log.info(
            f'membership revoke success: user_id={user_id}, family={tier.family_code}, '
            f'delta_days={delta_days}, new_valid_to={new_valid_to}, status={new_status}'
        )
        return membership

    @staticmethod
    async def get_user_membership_info(db: AsyncSession, *, user_id: int) -> Sequence[UserMembership]:
        """
        获取用户当前生效会员

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await user_membership_dao.get_active_by_user(db, user_id)

    @staticmethod
    async def get_user_records(
        db: AsyncSession,
        *,
        user_id: int,
        family_code: str | None = None,
        plan_id: int | None = None,
        tier_id: int | None = None,
    ) -> Select:
        """
        获取用户会员流水分页语句

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param family_code: 族群编码
        :param plan_id: 计划 ID
        :param tier_id: 等级 ID
        :return:
        """
        return await membership_record_dao.get_select(
            user_id=user_id,
            family_code=family_code,
            plan_id=plan_id,
            tier_id=tier_id,
        )

    @staticmethod
    async def check_and_expire_memberships() -> int:
        """
        同步处理已过期会员记录

        :return:
        """
        affected_user_ids: set[int] = set()
        async with async_db_session.begin() as db:
            expired_records = await user_membership_dao.get_expired(db)
            if not expired_records:
                return 0

            expired_ids = [record.id for record in expired_records]
            affected_user_ids = {record.user_id for record in expired_records}
            await user_membership_dao.mark_expired(db, expired_ids)

        if affected_user_ids:
            await user_cache_manager.clear(list(affected_user_ids))

        log.info(f'membership expire sync done: {len(affected_user_ids)} users affected')
        return len(affected_user_ids)


membership_service: MembershipService = MembershipService()
