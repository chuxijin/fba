#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.membership.crud.crud_membership import user_membership_dao
from backend.app.membership.crud.crud_record import membership_record_dao
from backend.app.membership.crud.crud_tier import membership_tier_dao
from backend.app.membership.model.record import MembershipRecord
from backend.common.exception import errors
from backend.common.log import log


class MembershipExperienceService:
    """会员经验服务"""

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
            membership = await user_membership_dao.get_by_user_and_family(db, user_id, family_code)
            if not membership:
                raise errors.RequestError(msg='经验流水存在但会员状态不存在，请人工处理')
            next_tier = await membership_tier_dao.get_next_tier(
                db,
                family_code=family_code,
                current_grade=membership.tier_grade,
            )
            next_exp_required = next_tier.exp_required if next_tier else None
            return {
                'family_code': membership.family_code,
                'tier_id': membership.tier_id,
                'tier_grade': membership.tier_grade,
                'exp': membership.exp,
                'next_exp_required': next_exp_required,
            }

        membership = await user_membership_dao.get_by_user_and_family(
            db,
            user_id,
            family_code,
            for_update=True,
        )
        if not membership or membership.status != 1:
            raise errors.ForbiddenError(msg='当前族群没有生效会员，无法累计经验')

        new_exp = membership.exp + exp_delta
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
                'tier_id': target_tier.id,
                'tier_code': target_tier.code,
                'tier_name': target_tier.name,
                'tier_grade': target_tier.grade,
                'tier_weight': target_tier.weight,
            },
        )
        membership.exp = new_exp
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

        next_tier = await membership_tier_dao.get_next_tier(
            db,
            family_code=family_code,
            current_grade=target_tier.grade,
        )
        next_exp_required = next_tier.exp_required if next_tier else None
        return {
            'family_code': membership.family_code,
            'tier_id': membership.tier_id,
            'tier_grade': membership.tier_grade,
            'exp': membership.exp,
            'next_exp_required': next_exp_required,
        }

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
            next_tier = await membership_tier_dao.get_next_tier(
                db,
                family_code=membership.family_code,
                current_grade=membership.tier_grade,
            )
            next_exp_required = next_tier.exp_required if next_tier else None
            data.append({
                'family_code': membership.family_code,
                'tier_id': membership.tier_id,
                'tier_grade': membership.tier_grade,
                'exp': membership.exp,
                'next_exp_required': next_exp_required,
            })
        return data


membership_experience_service: MembershipExperienceService = MembershipExperienceService()
