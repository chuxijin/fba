#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import secrets
import string

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.invite.crud.crud_invite import (
    invite_code_dao,
    invite_relation_dao,
    invite_reward_rule_dao,
)
from backend.app.invite.model import InviteCode, InviteRelation
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
from backend.common.events import publish
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
        charset = string.ascii_uppercase + string.digits
        for char in 'O0I1':
            charset = charset.replace(char, '')
        return ''.join(secrets.choice(charset) for _ in range(length))

    @staticmethod
    def _build_reward_payload(
        *,
        reward_data: dict | None,
        relation_id: int,
        reward_target: str,
        inviter_user_id: int,
        invitee_user_id: int,
    ) -> dict:
        """
        构建奖励发放参数

        :param reward_data: 原始奖励数据
        :param relation_id: 邀请关系 ID
        :param reward_target: 奖励对象
        :param inviter_user_id: 邀请人用户 ID
        :param invitee_user_id: 被邀请人用户 ID
        :return:
        """
        payload = dict(reward_data or {})
        payload['source'] = 'invite'
        payload['source_key'] = f'invite:{relation_id}:{reward_target}'
        payload.setdefault(
            'source_detail',
            f'invite_relation={relation_id},inviter={inviter_user_id},invitee={invitee_user_id}',
        )
        payload.setdefault('remark', '邀请奖励')
        return payload

    @staticmethod
    async def _resolve_reward_rule_id(db: AsyncSession, reward_rule_id: int | None) -> int | None:
        """
        解析邀请码使用的奖励规则

        :param db: 数据库会话
        :param reward_rule_id: 指定奖励规则 ID
        :return:
        """
        if reward_rule_id:
            rule = await invite_reward_rule_dao.select_model(db, reward_rule_id)
            if not rule:
                raise errors.NotFoundError(msg='奖励规则不存在')
            return reward_rule_id

        default_rule = await invite_reward_rule_dao.get_current_default(db)
        if not default_rule:
            return None
        return default_rule.id

    @staticmethod
    async def create_code(*, db: AsyncSession, user_id: int, obj: CreateInviteCodeParam) -> GetInviteCodeDetail:
        """
        为用户创建邀请码

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 创建参数
        :return:
        """
        reward_rule_id = await InviteService._resolve_reward_rule_id(db, obj.reward_rule_id)

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
        dict_obj['reward_rule_id'] = reward_rule_id
        invite_code = InviteCode(**dict_obj)
        db.add(invite_code)
        await db.commit()
        await db.refresh(invite_code)
        return GetInviteCodeDetail.model_validate(invite_code)

    @staticmethod
    async def get_my_code(
        *,
        db: AsyncSession,
        user_id: int,
        campaign_id: int | None = None,
    ) -> GetInviteCodeDetail | None:
        """
        获取当前用户邀请码

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param campaign_id: 活动 ID
        :return:
        """
        invite_code = await invite_code_dao.get_by_user(db, user_id, campaign_id)
        if invite_code:
            if invite_code.reward_rule_id is None:
                reward_rule_id = await InviteService._resolve_reward_rule_id(db, None)
                if reward_rule_id:
                    invite_code.reward_rule_id = reward_rule_id
                    await db.commit()
                    await db.refresh(invite_code)
            return GetInviteCodeDetail.model_validate(invite_code)

        obj = CreateInviteCodeParam(campaign_id=campaign_id, channel='miniapp')
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
        invite_code = await invite_code_dao.get_by_code(db, obj.code)
        if not invite_code:
            return AcceptInviteResult(success=False, message='邀请码不存在')

        if invite_code.status != 1:
            return AcceptInviteResult(success=False, message='邀请码已停用')

        if invite_code.user_id == invitee_user_id:
            return AcceptInviteResult(success=False, message='不能使用自己的邀请码')

        already_invited = await invite_relation_dao.check_already_invited(db, invitee_user_id)
        if already_invited:
            return AcceptInviteResult(success=False, message='您已接受过邀请码')

        if invite_code.max_uses > 0 and invite_code.used_count >= invite_code.max_uses:
            return AcceptInviteResult(success=False, message='该邀请码已达使用上限')

        rule = None
        if invite_code.reward_rule_id:
            rule = await invite_reward_rule_dao.select_model(db, invite_code.reward_rule_id)
            if rule and rule.status == 1:
                now = timezone.now()
                if rule.valid_from and now < rule.valid_from:
                    return AcceptInviteResult(success=False, message='邀请活动尚未开始')
                if rule.valid_to and now > rule.valid_to:
                    return AcceptInviteResult(success=False, message='邀请活动已结束')

                if rule.max_invites_per_user > 0:
                    invite_count = await invite_relation_dao.get_invite_count(db, invite_code.user_id)
                    if invite_count >= rule.max_invites_per_user:
                        return AcceptInviteResult(success=False, message='邀请人已达邀请上限')

        relation = InviteRelation(
            invite_code_id=invite_code.id,
            inviter_user_id=invite_code.user_id,
            invitee_user_id=invitee_user_id,
            channel=obj.channel,
            ip_address=obj.ip_address,
        )
        db.add(relation)
        await db.flush()

        await invite_code_dao.increment_used_count(db, invite_code.id)

        if rule and rule.status == 1:
            inviter_ok = await dispatch_reward(
                db=db,
                user_id=invite_code.user_id,
                reward_type=rule.inviter_reward_type,
                reward_data=InviteService._build_reward_payload(
                    reward_data=rule.inviter_reward_data,
                    relation_id=relation.id,
                    reward_target='inviter',
                    inviter_user_id=invite_code.user_id,
                    invitee_user_id=invitee_user_id,
                ),
            )
            relation.inviter_reward_status = 1 if inviter_ok else 2

            if rule.invitee_reward_type and rule.invitee_reward_data:
                invitee_ok = await dispatch_reward(
                    db=db,
                    user_id=invitee_user_id,
                    reward_type=rule.invitee_reward_type,
                    reward_data=InviteService._build_reward_payload(
                        reward_data=rule.invitee_reward_data,
                        relation_id=relation.id,
                        reward_target='invitee',
                        inviter_user_id=invite_code.user_id,
                        invitee_user_id=invitee_user_id,
                    ),
                )
                relation.invitee_reward_status = 1 if invitee_ok else 2

        await db.commit()
        await publish(
            'invite.accepted',
            inviter_user_id=invite_code.user_id,
            invitee_user_id=invitee_user_id,
            relation_id=relation.id,
        )
        return AcceptInviteResult(success=True, message='邀请成功')

    @staticmethod
    async def get_invite_list(
        *,
        db: AsyncSession,
        inviter_user_id: int | None = None,
        invitee_user_id: int | None = None,
    ) -> dict[str, Any]:
        """
        获取邀请关系列表

        :param db: 数据库会话
        :param inviter_user_id: 邀请人用户 ID
        :param invitee_user_id: 被邀请人用户 ID
        :return:
        """
        relation_select = await invite_relation_dao.get_select(
            inviter_user_id=inviter_user_id,
            invitee_user_id=invitee_user_id,
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
        return await invite_reward_rule_dao.update_model(db, pk, obj)

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
