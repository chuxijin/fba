#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_role import role_dao
from backend.app.membership.crud.crud_plan import membership_plan_dao
from backend.app.membership.crud.crud_tier import membership_tier_dao
from backend.app.membership.model.plan import MembershipPlan
from backend.app.membership.schema.plan import CreateMembershipPlanParam, UpdateMembershipPlanParam
from backend.common.exception import errors


class MembershipPlanService:
    """会员计划服务"""

    @staticmethod
    async def get_select(
        *,
        name: str | None = None,
        status: int | None = None,
        tier_id: int | None = None,
    ) -> Select:
        """
        获取会员计划分页查询语句

        :param name: 计划名称
        :param status: 状态
        :param tier_id: 会员等级 ID
        :return:
        """
        return await membership_plan_dao.get_select(name=name, status=status, tier_id=tier_id)

    @staticmethod
    async def get(db: AsyncSession, *, pk: int) -> MembershipPlan:
        """
        获取会员计划详情

        :param db: 数据库会话
        :param pk: 计划 ID
        :return:
        """
        plan = await membership_plan_dao.select_model(db, pk)
        if not plan:
            raise errors.NotFoundError(msg='会员计划不存在')
        return plan

    @staticmethod
    async def create(db: AsyncSession, *, obj: CreateMembershipPlanParam) -> None:
        """
        创建会员计划

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        existing = await membership_plan_dao.get_by_name(db, obj.name)
        if existing:
            raise errors.ConflictError(msg='计划名称已存在')

        tier = await membership_tier_dao.select_model(db, obj.tier_id)
        if not tier:
            raise errors.NotFoundError(msg='会员等级不存在')
        if tier.status != 1:
            raise errors.RequestError(msg='会员等级已停用')

        role = await role_dao.get(db, obj.role_id)
        if not role:
            raise errors.NotFoundError(msg='关联角色不存在')

        await membership_plan_dao.create_model(db, obj)

    @staticmethod
    async def update(db: AsyncSession, *, pk: int, obj: UpdateMembershipPlanParam) -> int:
        """
        更新会员计划

        :param db: 数据库会话
        :param pk: 计划 ID
        :param obj: 更新参数
        :return:
        """
        plan = await membership_plan_dao.select_model(db, pk)
        if not plan:
            raise errors.NotFoundError(msg='会员计划不存在')

        if obj.name and obj.name != plan.name:
            existing = await membership_plan_dao.get_by_name(db, obj.name)
            if existing:
                raise errors.ConflictError(msg='计划名称已存在')

        if obj.tier_id is not None:
            tier = await membership_tier_dao.select_model(db, obj.tier_id)
            if not tier:
                raise errors.NotFoundError(msg='会员等级不存在')
            if tier.status != 1:
                raise errors.RequestError(msg='会员等级已停用')

        if obj.role_id is not None:
            role = await role_dao.get(db, obj.role_id)
            if not role:
                raise errors.NotFoundError(msg='关联角色不存在')

        return await membership_plan_dao.update_model(db, pk, obj)

    @staticmethod
    async def delete(db: AsyncSession, *, pk: int) -> int:
        """
        删除会员计划

        :param db: 数据库会话
        :param pk: 计划 ID
        :return:
        """
        plan = await membership_plan_dao.select_model(db, pk)
        if not plan:
            raise errors.NotFoundError(msg='会员计划不存在')
        return await membership_plan_dao.delete_model(db, pk)

    @staticmethod
    async def get_active_plans(db: AsyncSession) -> Sequence[MembershipPlan]:
        """
        获取上架计划

        :param db: 数据库会话
        :return:
        """
        return await membership_plan_dao.get_active_plans(db)


membership_plan_service: MembershipPlanService = MembershipPlanService()
