#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.membership.crud.crud_membership import user_membership_dao
from backend.app.membership.crud.crud_record import membership_record_dao
from backend.app.membership.crud.crud_tier import membership_tier_dao
from backend.app.membership.model.membership import UserMembership
from backend.app.membership.model.record import MembershipRecord
from backend.common.exception import errors
from backend.common.log import log


class MembershipExperienceService:
    """会员经验服务"""

    @staticmethod
    async def resolve_reward_family(db: AsyncSession, *, user_id: int) -> str:
        """
        解析用户经验入账族群

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        memberships = await user_membership_dao.get_active_by_user(db, user_id)
        if memberships:
            return memberships[0].family_code
        return 'FREE'

    @staticmethod
    async def _ensure_membership(
        db: AsyncSession,
        *,
        user_id: int,
        family_code: str,
        for_update: bool = False,
    ) -> UserMembership:
        """
        确保经验账户存在

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param family_code: 族群编码
        :param for_update: 是否加行锁
        :return:
        """
        membership = await user_membership_dao.get_by_user_and_family(
            db,
            user_id,
            family_code,
            for_update=for_update,
        )
        if membership and membership.status == 1:
            return membership

        if family_code != 'FREE':
            raise errors.ForbiddenError(msg='当前族群没有生效会员，无法累计经验')

        tier = await membership_tier_dao.get_highest_tier_by_exp(
            db,
            family_code=family_code,
            exp=0,
        )
        if not tier:
            raise errors.RequestError(msg='免费会员等级配置缺失')

        membership = UserMembership(
            user_id=user_id,
            family_code=tier.family_code,
            tier_id=tier.id,
            tier_code=tier.code,
            tier_name=tier.name,
            tier_grade=tier.grade,
            tier_weight=tier.weight,
            exp=0,
            available_exp=0,
            valid_from=None,
            valid_to=None,
            source='system',
            source_key=f'free:{user_id}',
            status=1,
            remark='自动创建免费经验账户',
        )
        db.add(membership)
        await db.flush()
        return membership

    @staticmethod
    async def _build_progress_payload(
        db: AsyncSession,
        membership: UserMembership,
    ) -> dict[str, int | str | None]:
        """
        构建经验进度返回数据

        :param db: 数据库会话
        :param membership: 会员状态
        :return:
        """
        next_tier = await membership_tier_dao.get_next_tier(
            db,
            family_code=membership.family_code,
            current_grade=membership.tier_grade,
        )
        next_exp_required = next_tier.exp_required if next_tier else None
        return {
            'family_code': membership.family_code,
            'tier_id': membership.tier_id,
            'tier_grade': membership.tier_grade,
            'exp': membership.exp,
            'available_exp': membership.available_exp,
            'next_exp_required': next_exp_required,
        }

    @staticmethod
    async def add_experience(
        db: AsyncSession,
        *,
        user_id: int,
        family_code: str,
        exp_delta: int,
        source: str,
        source_key: str,
        remark: str | None = None,
    ) -> dict[str, int | str | None]:
        """
        增加经验并自动升级等级

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param family_code: 族群编码
        :param exp_delta: 经验增量
        :param source: 来源标识
        :param source_key: 来源幂等键
        :param remark: 备注
        :return:
        """
        if exp_delta <= 0:
            raise errors.RequestError(msg='经验增量必须大于 0')
        if not source_key:
            raise errors.RequestError(msg='source_key 不能为空')

        idempotent = await membership_record_dao.get_by_idempotency(
            db,
            user_id=user_id,
            family_code=family_code,
            source=source,
            source_key=source_key,
            op_type='exp_add',
        )
        if idempotent:
            membership = await MembershipExperienceService._ensure_membership(
                db,
                user_id=user_id,
                family_code=family_code,
            )
            if not membership:
                raise errors.RequestError(msg='经验流水存在但会员状态不存在，请人工处理')
            return await MembershipExperienceService._build_progress_payload(db, membership)

        membership = await MembershipExperienceService._ensure_membership(
            db,
            user_id=user_id,
            family_code=family_code,
            for_update=True,
        )

        new_exp = membership.exp + exp_delta
        new_available_exp = membership.available_exp + exp_delta
        target_tier = await membership_tier_dao.get_highest_tier_by_exp(
            db,
            family_code=family_code,
            exp=new_exp,
        )
        if not target_tier:
            raise errors.RequestError(msg='会员等级配置缺失')

        upgraded = target_tier.weight > membership.tier_weight
        await user_membership_dao.update_model(
            db,
            membership.id,
            {
                'exp': new_exp,
                'available_exp': new_available_exp,
                'tier_id': target_tier.id,
                'tier_code': target_tier.code,
                'tier_name': target_tier.name,
                'tier_grade': target_tier.grade,
                'tier_weight': target_tier.weight,
            },
        )
        membership.exp = new_exp
        membership.available_exp = new_available_exp
        membership.tier_id = target_tier.id
        membership.tier_code = target_tier.code
        membership.tier_name = target_tier.name
        membership.tier_grade = target_tier.grade
        membership.tier_weight = target_tier.weight

        record = MembershipRecord(
            user_id=user_id,
            family_code=family_code,
            tier_id=target_tier.id,
            plan_id=None,
            op_type='exp_add',
            days=0,
            exp_delta=exp_delta,
            source=source,
            source_key=source_key,
            source_detail=None,
            valid_to_before=membership.valid_to,
            valid_to_after=membership.valid_to,
            remark=remark,
        )
        db.add(record)

        if upgraded:
            log.info(
                f'membership tier upgraded by exp: user_id={user_id}, family={family_code}, '
                f'tier={target_tier.code}, grade={target_tier.grade}, exp={new_exp}'
            )

        return await MembershipExperienceService._build_progress_payload(db, membership)

    @staticmethod
    async def consume_experience(
        db: AsyncSession,
        *,
        user_id: int,
        family_code: str,
        exp_delta: int,
        source: str,
        source_key: str,
        remark: str | None = None,
    ) -> dict[str, int | str | None]:
        """
        消耗可用经验

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param family_code: 族群编码
        :param exp_delta: 消耗经验值
        :param source: 来源标识
        :param source_key: 来源幂等键
        :param remark: 备注
        :return:
        """
        if exp_delta <= 0:
            raise errors.RequestError(msg='消耗经验必须大于 0')
        if not source_key:
            raise errors.RequestError(msg='source_key 不能为空')

        idempotent = await membership_record_dao.get_by_idempotency(
            db,
            user_id=user_id,
            family_code=family_code,
            source=source,
            source_key=source_key,
            op_type='exp_consume',
        )
        if idempotent:
            membership = await MembershipExperienceService._ensure_membership(
                db,
                user_id=user_id,
                family_code=family_code,
            )
            return await MembershipExperienceService._build_progress_payload(db, membership)

        membership = await MembershipExperienceService._ensure_membership(
            db,
            user_id=user_id,
            family_code=family_code,
            for_update=True,
        )
        if membership.available_exp < exp_delta:
            raise errors.RequestError(msg='可用经验不足')

        new_available_exp = membership.available_exp - exp_delta
        await user_membership_dao.update_model(
            db,
            membership.id,
            {'available_exp': new_available_exp},
        )
        membership.available_exp = new_available_exp

        record = MembershipRecord(
            user_id=user_id,
            family_code=family_code,
            tier_id=membership.tier_id,
            plan_id=None,
            op_type='exp_consume',
            days=0,
            exp_delta=-exp_delta,
            source=source,
            source_key=source_key,
            source_detail=None,
            valid_to_before=membership.valid_to,
            valid_to_after=membership.valid_to,
            remark=remark,
        )
        db.add(record)
        return await MembershipExperienceService._build_progress_payload(db, membership)

    @staticmethod
    async def get_user_progress(
        db: AsyncSession,
        *,
        user_id: int,
        family_code: str | None = None,
    ) -> list[dict[str, int | str | None]]:
        """
        查询用户经验进度

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param family_code: 族群编码
        :return:
        """
        memberships = await user_membership_dao.get_active_by_user(db, user_id)
        if family_code:
            memberships = [item for item in memberships if item.family_code == family_code]

        data: list[dict[str, int | str | None]] = []
        for membership in memberships:
            data.append(await MembershipExperienceService._build_progress_payload(db, membership))
        return data


membership_experience_service: MembershipExperienceService = MembershipExperienceService()
