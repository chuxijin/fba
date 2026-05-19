#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.invite.model import InviteCode, InviteRelation, InviteRewardRule
from backend.app.invite.schema.invite import CreateRewardRuleParam
from backend.utils.timezone import timezone


class CRUDInviteCode(CRUDPlus[InviteCode]):
    """邀请码数据库操作类"""

    async def get_by_code(self, db: AsyncSession, code: str) -> InviteCode | None:
        """
        根据邀请码获取记录

        :param db: 数据库会话
        :param code: 邀请码
        :return:
        """
        return await self.select_model_by_column(db, code__eq=code)

    async def get_by_user(self, db: AsyncSession, user_id: int, campaign_id: int | None = None) -> InviteCode | None:
        """
        获取用户的邀请码

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param campaign_id: 活动 ID
        :return:
        """
        filters = {'user_id__eq': user_id}
        if campaign_id is not None:
            filters['campaign_id__eq'] = campaign_id
        return await self.select_model_by_column(db, **filters)

    async def get_select(
        self, user_id: int | None = None, status: int | None = None, campaign_id: int | None = None
    ) -> Select:
        """
        获取邀请码列表查询表达式

        :param user_id: 用户 ID
        :param status: 状态
        :param campaign_id: 活动 ID
        :return:
        """
        filters = {}
        if user_id is not None:
            filters['user_id__eq'] = user_id
        if status is not None:
            filters['status__eq'] = status
        if campaign_id is not None:
            filters['campaign_id__eq'] = campaign_id
        return await self.select_order('created_time', 'desc', **filters)

    async def increment_used_count(self, db: AsyncSession, pk: int) -> None:
        """
        增加已使用次数

        :param db: 数据库会话
        :param pk: 邀请码 ID
        :return:
        """
        invite_code = await self.select_model(db, pk)
        if invite_code:
            await self.update_model(db, pk, {'used_count': invite_code.used_count + 1}, commit=False)


class CRUDInviteRelation(CRUDPlus[InviteRelation]):
    """邀请关系数据库操作类"""

    async def check_already_invited(self, db: AsyncSession, invitee_user_id: int) -> bool:
        """
        检查用户是否已被邀请过

        :param db: 数据库会话
        :param invitee_user_id: 被邀请人用户 ID
        :return:
        """
        result = await self.select_model_by_column(db, invitee_user_id__eq=invitee_user_id)
        return result is not None

    async def get_invite_count(self, db: AsyncSession, inviter_user_id: int) -> int:
        """
        获取用户邀请总数

        :param db: 数据库会话
        :param inviter_user_id: 邀请人用户 ID
        :return:
        """
        stmt = select(func.count()).where(InviteRelation.inviter_user_id == inviter_user_id)
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def get_select(
        self, inviter_user_id: int | None = None, invitee_user_id: int | None = None
    ) -> Select:
        """
        获取邀请关系列表查询表达式

        :param inviter_user_id: 邀请人用户 ID
        :param invitee_user_id: 被邀请人用户 ID
        :return:
        """
        filters = {}
        if inviter_user_id is not None:
            filters['inviter_user_id__eq'] = inviter_user_id
        if invitee_user_id is not None:
            filters['invitee_user_id__eq'] = invitee_user_id
        return await self.select_order('created_time', 'desc', **filters)


class CRUDInviteRewardRule(CRUDPlus[InviteRewardRule]):
    """邀请奖励规则数据库操作类"""

    async def create(self, db: AsyncSession, obj: CreateRewardRuleParam) -> InviteRewardRule:
        """
        创建奖励规则

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        return await self.create_model(db, obj.model_dump(), commit=False)

    async def get_select(self, status: int | None = None) -> Select:
        """
        获取奖励规则列表查询表达式

        :param status: 状态
        :return:
        """
        filters = {}
        if status is not None:
            filters['status__eq'] = status
        return await self.select_order('created_time', 'desc', **filters)

    async def get_current_default(self, db: AsyncSession) -> InviteRewardRule | None:
        """获取当前有效的默认奖励规则"""
        now = timezone.now()
        stmt = (
            select(self.model)
            .where(
                self.model.status == 1,
                or_(self.model.valid_from.is_(None), self.model.valid_from <= now),
                or_(self.model.valid_to.is_(None), self.model.valid_to > now),
            )
            .order_by(self.model.created_time.desc(), self.model.id.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first()


invite_code_dao: CRUDInviteCode = CRUDInviteCode(InviteCode)
invite_relation_dao: CRUDInviteRelation = CRUDInviteRelation(InviteRelation)
invite_reward_rule_dao: CRUDInviteRewardRule = CRUDInviteRewardRule(InviteRewardRule)
