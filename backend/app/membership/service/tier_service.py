#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.membership.crud.crud_tier import membership_tier_dao
from backend.app.membership.model.plan import MembershipPlan
from backend.app.membership.model.tier import MembershipTier
from backend.app.membership.schema.tier import CreateMembershipTierParam, UpdateMembershipTierParam
from backend.common.exception import errors


class MembershipTierService:
    """会员等级服务"""

    @staticmethod
    async def get_select(
        *,
        name: str | None = None,
        status: int | None = None,
        family_code: str | None = None,
    ) -> Select:
        """
        获取会员等级分页查询语句

        :param name: 等级名称
        :param status: 状态
        :param family_code: 族群编码
        :return:
        """
        return await membership_tier_dao.get_select(name=name, status=status, family_code=family_code)

    @staticmethod
    async def get(db: AsyncSession, *, pk: int) -> MembershipTier:
        """
        获取等级详情

        :param db: 数据库会话
        :param pk: 等级 ID
        :return:
        """
        tier = await membership_tier_dao.select_model(db, pk)
        if not tier:
            raise errors.NotFoundError(msg='会员等级不存在')
        return tier

    @staticmethod
    async def create(db: AsyncSession, *, obj: CreateMembershipTierParam) -> None:
        """
        创建会员等级

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        existing_code = await membership_tier_dao.get_by_code(db, obj.code)
        if existing_code:
            raise errors.ConflictError(msg='等级编码已存在')

        existing_weight = await membership_tier_dao.get_by_weight(db, obj.weight)
        if existing_weight:
            raise errors.ConflictError(msg='等级权重已存在')

        if obj.family_code in {'VIP', 'SVIP'} and (obj.grade < 1 or obj.grade > 10):
            raise errors.RequestError(msg='VIP/SVIP 等级必须在 1~10')

        existing_grade = await membership_tier_dao.get_by_family_grade(db, obj.family_code, obj.grade)
        if existing_grade:
            raise errors.ConflictError(msg='该族群等级已存在')

        if obj.is_default:
            if obj.family_code != 'FREE' or obj.grade != 0:
                raise errors.RequestError(msg='默认等级必须是 FREE-0')
            await membership_tier_dao.clear_default(db)

        await membership_tier_dao.create_model(db, obj)

    @staticmethod
    async def update(db: AsyncSession, *, pk: int, obj: UpdateMembershipTierParam) -> int:
        """
        更新会员等级

        :param db: 数据库会话
        :param pk: 等级 ID
        :param obj: 更新参数
        :return:
        """
        tier = await membership_tier_dao.select_model(db, pk)
        if not tier:
            raise errors.NotFoundError(msg='会员等级不存在')

        if obj.code and obj.code != tier.code:
            existing_code = await membership_tier_dao.get_by_code(db, obj.code)
            if existing_code:
                raise errors.ConflictError(msg='等级编码已存在')

        if obj.weight is not None and obj.weight != tier.weight:
            existing_weight = await membership_tier_dao.get_by_weight(db, obj.weight)
            if existing_weight:
                raise errors.ConflictError(msg='等级权重已存在')

        target_family = obj.family_code if obj.family_code is not None else tier.family_code
        target_grade = obj.grade if obj.grade is not None else tier.grade
        if target_family in {'VIP', 'SVIP'} and (target_grade < 1 or target_grade > 10):
            raise errors.RequestError(msg='VIP/SVIP 等级必须在 1~10')

        if target_family != tier.family_code or target_grade != tier.grade:
            existing_grade = await membership_tier_dao.get_by_family_grade(db, target_family, target_grade)
            if existing_grade and existing_grade.id != tier.id:
                raise errors.ConflictError(msg='该族群等级已存在')

        if obj.is_default:
            if target_family != 'FREE' or target_grade != 0:
                raise errors.RequestError(msg='默认等级必须是 FREE-0')
            await membership_tier_dao.clear_default(db)

        return await membership_tier_dao.update_model(db, pk, obj)

    @staticmethod
    async def delete(db: AsyncSession, *, pk: int) -> int:
        """
        删除会员等级

        :param db: 数据库会话
        :param pk: 等级 ID
        :return:
        """
        tier = await membership_tier_dao.select_model(db, pk)
        if not tier:
            raise errors.NotFoundError(msg='会员等级不存在')

        if tier.is_default:
            raise errors.RequestError(msg='默认等级不允许删除')

        stmt = select(MembershipPlan.id).where(MembershipPlan.tier_id == pk).limit(1)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise errors.RequestError(msg='该等级已被会员计划使用，无法删除')

        return await membership_tier_dao.delete_model(db, pk)

    @staticmethod
    async def get_active_tiers(db: AsyncSession) -> Sequence[MembershipTier]:
        """
        获取启用等级

        :param db: 数据库会话
        :return:
        """
        return await membership_tier_dao.get_active_tiers(db)


membership_tier_service: MembershipTierService = MembershipTierService()
