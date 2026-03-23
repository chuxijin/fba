#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import secrets
import string
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.invite.crud.crud_invite import invite_code_dao, invite_relation_dao, invite_reward_rule_dao
from backend.app.invite.model import InviteRelation
from backend.app.invite.schema.invite import (
    AcceptInviteParam,
    AcceptInviteResult,
    CreateInviteCodeParam,
    CreateRewardRuleParam,
    GetInviteCodeDetail,
    GetRewardRuleDetail,
    UpdateRewardRuleParam,
)
from backend.common.exception import errors
from backend.common.log import log
from backend.common.pagination import paging_data
from backend.common.reward import dispatch_reward
from backend.utils.timezone import timezone


class InviteService:
    """邀请码服务类"""

    @staticmethod
    def _generate_invite_code(length: int = 8) -> str:
        """
        生成邀请码

        :param length: 邀请码长度
        :return:
        """
        # 排除易混淆字符
        charset = string.ascii_uppercase + string.digits
        for char in 'O0I1':
            charset = charset.replace(char, '')
        return ''.join(secrets.choice(charset) for _ in range(length))

    @staticmethod
    async def create_code(*, db: AsyncSession, user_id: int, obj: CreateInviteCodeParam) -> GetInviteCodeDetail:
        """
        为用户创建邀请码

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 创建参数
        :return:
        """
        # 校验奖励规则是否存在
        if obj.reward_rule_id:
            rule = await invite_reward_rule_dao.select_model(db, obj.reward_rule_id)
            if not rule:
                raise errors.NotFoundError(msg='奖励规则不存在')

        # 生成唯一邀请码（重试机制）
        for _ in range(10):
            code = InviteService._generate_invite_code()
            existing = await invite_code_dao.get_by_code(db, code)
            if not existing:
                break
        else:
            raise errors.ServerError(msg='邀请码生成失败，请重试')

        dict_obj = obj.model_dump()
        dict_obj['user_id'] = user_id
        dict_obj['code'] = code
        invite_code = await invite_code_dao.create_model(db, dict_obj, commit=False)
        await db.commit()
        await db.refresh(invite_code)
        return GetInviteCodeDetail.model_validate(invite_code)

    @staticmethod
    async def get_my_code(
        *, db: AsyncSession, user_id: int, campaign_id: int | None = None
    ) -> GetInviteCodeDetail | None:
        """
        获取用户的邀请码（如果不存在则自动创建默认邀请码）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param campaign_id: 活动 ID
        :return:
        """
        invite_code = await invite_code_dao.get_by_user(db, user_id, campaign_id)
        if invite_code:
            return GetInviteCodeDetail.model_validate(invite_code)

        # 自动创建默认邀请码
        obj = CreateInviteCodeParam(campaign_id=campaign_id)
        return await InviteService.create_code(db=db, user_id=user_id, obj=obj)

    @staticmethod
    async def get_code_list(
        *,
        db: AsyncSession,
        user_id: int | None = None,
        status: int | None = None,
        campaign_id: int | None = None,
    ) -> dict[str, Any]:
        """
        获取邀请码列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param status: 状态
        :param campaign_id: 活动 ID
        :return:
        """
        code_select = await invite_code_dao.get_select(user_id=user_id, status=status, campaign_id=campaign_id)
        return await paging_data(db, code_select)

    @staticmethod
    async def accept_invite(*, db: AsyncSession, invitee_user_id: int, obj: AcceptInviteParam) -> AcceptInviteResult:
        """
        接受邀请

        :param db: 数据库会话
        :param invitee_user_id: 被邀请人用户 ID
        :param obj: 接受邀请参数
        :return:
        """
        # 查找邀请码
        invite_code = await invite_code_dao.get_by_code(db, obj.code)
        if not invite_code:
            return AcceptInviteResult(success=False, message='邀请码不存在')

        if invite_code.status != 1:
            return AcceptInviteResult(success=False, message='邀请码已停用')

        # 不能邀请自己
        if invite_code.user_id == invitee_user_id:
            return AcceptInviteResult(success=False, message='不能使用自己的邀请码')

        # 检查是否已被邀请过
        already_invited = await invite_relation_dao.check_already_invited(db, invitee_user_id)
        if already_invited:
            return AcceptInviteResult(success=False, message='您已接受过邀请')

        # 检查使用次数限制
        if invite_code.max_uses > 0 and invite_code.used_count >= invite_code.max_uses:
            return AcceptInviteResult(success=False, message='该邀请码已达使用上限')

        # 校验奖励规则
        rule = None
        if invite_code.reward_rule_id:
            rule = await invite_reward_rule_dao.select_model(db, invite_code.reward_rule_id)
            if rule and rule.status == 1:
                # 校验规则有效期
                now = timezone.now()
                if rule.valid_from and now < rule.valid_from:
                    return AcceptInviteResult(success=False, message='邀请活动尚未开始')
                if rule.valid_to and now > rule.valid_to:
                    return AcceptInviteResult(success=False, message='邀请活动已结束')

                # 校验邀请人邀请上限
                if rule.max_invites_per_user > 0:
                    invite_count = await invite_relation_dao.get_invite_count(db, invite_code.user_id)
                    if invite_count >= rule.max_invites_per_user:
                        return AcceptInviteResult(success=False, message='邀请人已达邀请上限')

        # 创建邀请关系
        relation = InviteRelation(
            invite_code_id=invite_code.id,
            inviter_user_id=invite_code.user_id,
            invitee_user_id=invitee_user_id,
            channel=obj.channel,
            ip_address=obj.ip_address,
        )
        db.add(relation)

        # 更新邀请码使用次数
        await invite_code_dao.increment_used_count(db, invite_code.id)

        # 发放奖励
        if rule and rule.status == 1:
            # 发放邀请人奖励
            inviter_ok = await dispatch_reward(
                db=db,
                user_id=invite_code.user_id,
                reward_type=rule.inviter_reward_type,
                reward_data=rule.inviter_reward_data,
            )
            relation.inviter_reward_status = 1 if inviter_ok else 2

            # 发放被邀请人奖励（如果配置了）
            if rule.invitee_reward_type and rule.invitee_reward_data:
                invitee_ok = await dispatch_reward(
                    db=db,
                    user_id=invitee_user_id,
                    reward_type=rule.invitee_reward_type,
                    reward_data=rule.invitee_reward_data,
                )
                relation.invitee_reward_status = 1 if invitee_ok else 2

        await db.commit()
        return AcceptInviteResult(success=True, message='邀请成功')

    @staticmethod
    async def get_invite_list(
        *, db: AsyncSession, inviter_user_id: int | None = None, invitee_user_id: int | None = None
    ) -> dict[str, Any]:
        """
        获取邀请关系列表

        :param db: 数据库会话
        :param inviter_user_id: 邀请人用户 ID
        :param invitee_user_id: 被邀请人用户 ID
        :return:
        """
        relation_select = await invite_relation_dao.get_select(
            inviter_user_id=inviter_user_id, invitee_user_id=invitee_user_id
        )
        return await paging_data(db, relation_select)

    @staticmethod
    async def get_invite_stats(*, db: AsyncSession, user_id: int) -> dict[str, int]:
        """
        获取用户邀请统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        invite_count = await invite_relation_dao.get_invite_count(db, user_id)
        return {'total_invites': invite_count}

    # ============ 奖励规则管理 ============

    @staticmethod
    async def create_reward_rule(*, db: AsyncSession, obj: CreateRewardRuleParam) -> GetRewardRuleDetail:
        """
        创建奖励规则

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        rule = await invite_reward_rule_dao.create(db, obj)
        await db.commit()
        await db.refresh(rule)
        return GetRewardRuleDetail.model_validate(rule)

    @staticmethod
    async def update_reward_rule(*, db: AsyncSession, pk: int, obj: UpdateRewardRuleParam) -> int:
        """
        更新奖励规则

        :param db: 数据库会话
        :param pk: 规则 ID
        :param obj: 更新参数
        :return:
        """
        rule = await invite_reward_rule_dao.select_model(db, pk)
        if not rule:
            raise errors.NotFoundError(msg='奖励规则不存在')
        count = await invite_reward_rule_dao.update_model(db, pk, obj)
        return count

    @staticmethod
    async def get_reward_rule(*, db: AsyncSession, pk: int) -> GetRewardRuleDetail:
        """
        获取奖励规则详情

        :param db: 数据库会话
        :param pk: 规则 ID
        :return:
        """
        rule = await invite_reward_rule_dao.select_model(db, pk)
        if not rule:
            raise errors.NotFoundError(msg='奖励规则不存在')
        return GetRewardRuleDetail.model_validate(rule)

    @staticmethod
    async def get_reward_rule_list(*, db: AsyncSession, status: int | None = None) -> dict[str, Any]:
        """
        获取奖励规则列表

        :param db: 数据库会话
        :param status: 状态
        :return:
        """
        rule_select = await invite_reward_rule_dao.get_select(status=status)
        return await paging_data(db, rule_select)


invite_service: InviteService = InviteService()
