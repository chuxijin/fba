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
from backend.common.exception import errors
from backend.common.log import log
from backend.database.db import async_db_session
from backend.utils.timezone import timezone


class MembershipService:
    """会员服务"""

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
