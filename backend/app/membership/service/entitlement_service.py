#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.membership.crud.crud_entitlement import membership_entitlement_dao
from backend.app.membership.crud.crud_membership import user_membership_dao
from backend.app.membership.crud.crud_tier_entitlement import membership_tier_entitlement_dao
from backend.app.membership.model.entitlement import MembershipEntitlement
from backend.app.membership.model.tier_entitlement import MembershipTierEntitlement
from backend.app.membership.schema.entitlement import (
    CreateMembershipEntitlementParam,
    SetTierEntitlementsParam,
    UpdateMembershipEntitlementParam,
)
from backend.common.exception import errors


class MembershipEntitlementService:
    """会员权益服务"""

    @staticmethod
    async def get_select(*, name: str | None = None, status: int | None = None) -> Select:
        """
        获取权益分页查询语句

        :param name: 权益名称
        :param status: 状态
        :return:
        """
        return await membership_entitlement_dao.get_select(name=name, status=status)

    @staticmethod
    async def get(db: AsyncSession, *, pk: int) -> MembershipEntitlement:
        """
        获取权益详情

        :param db: 数据库会话
        :param pk: 权益 ID
        :return:
        """
        entitlement = await membership_entitlement_dao.select_model(db, pk)
        if not entitlement:
            raise errors.NotFoundError(msg='会员权益不存在')
        return entitlement

    @staticmethod
    async def create(db: AsyncSession, *, obj: CreateMembershipEntitlementParam) -> None:
        """
        创建权益

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        existing = await membership_entitlement_dao.get_by_code(db, obj.code)
        if existing:
            raise errors.ConflictError(msg='权益编码已存在')
        await membership_entitlement_dao.create_model(db, obj)

    @staticmethod
    async def update(db: AsyncSession, *, pk: int, obj: UpdateMembershipEntitlementParam) -> int:
        """
        更新权益

        :param db: 数据库会话
        :param pk: 权益 ID
        :param obj: 更新参数
        :return:
        """
        entitlement = await membership_entitlement_dao.select_model(db, pk)
        if not entitlement:
            raise errors.NotFoundError(msg='会员权益不存在')

        if obj.code and obj.code != entitlement.code:
            existing = await membership_entitlement_dao.get_by_code(db, obj.code)
            if existing:
                raise errors.ConflictError(msg='权益编码已存在')
        return await membership_entitlement_dao.update_model(db, pk, obj)

    @staticmethod
    async def delete(db: AsyncSession, *, pk: int) -> int:
        """
        删除权益

        :param db: 数据库会话
        :param pk: 权益 ID
        :return:
        """
        entitlement = await membership_entitlement_dao.select_model(db, pk)
        if not entitlement:
            raise errors.NotFoundError(msg='会员权益不存在')
        return await membership_entitlement_dao.delete_model(db, pk)

    @staticmethod
    async def set_tier_entitlements(
        db: AsyncSession,
        *,
        tier_id: int,
        obj: SetTierEntitlementsParam,
    ) -> None:
        """
        批量设置等级权益

        :param db: 数据库会话
        :param tier_id: 等级 ID
        :param obj: 权益参数
        :return:
        """
        await membership_tier_entitlement_dao.delete_by_tier(db, tier_id)
        if not obj.items:
            return

        for item in obj.items:
            entitlement = await membership_entitlement_dao.get_by_code(db, item.entitlement_code)
            if not entitlement:
                raise errors.NotFoundError(msg=f'权益编码不存在: {item.entitlement_code}')
            mapping = MembershipTierEntitlement(
                tier_id=tier_id,
                entitlement_id=entitlement.id,
                entitlement_code=entitlement.code,
                value=item.value,
                status=item.status,
                description=item.description,
            )
            db.add(mapping)

    @staticmethod
    async def get_tier_entitlements(db: AsyncSession, *, tier_id: int) -> Sequence[MembershipTierEntitlement]:
        """
        获取等级权益映射

        :param db: 数据库会话
        :param tier_id: 等级 ID
        :return:
        """
        return await membership_tier_entitlement_dao.get_by_tier(db, tier_id)

    @staticmethod
    async def check_user_entitlement(
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        required_value: int = 1,
    ) -> int:
        """
        校验用户权益值

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param required_value: 最低要求值
        :return:
        """
        memberships = await user_membership_dao.get_active_by_user(db, user_id)
        if not memberships:
            raise errors.ForbiddenError(msg='需要开通会员才能访问')

        best_value = 0
        for membership in memberships:
            item = await membership_tier_entitlement_dao.get_by_tier_and_code(
                db,
                tier_id=membership.tier_id,
                entitlement_code=entitlement_code,
            )
            if not item:
                continue
            if item.value > best_value:
                best_value = item.value

        if best_value < required_value:
            raise errors.ForbiddenError(msg='当前会员等级不满足权益要求')

        return best_value


membership_entitlement_service: MembershipEntitlementService = MembershipEntitlementService()
