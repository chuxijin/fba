#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ============ 邀请码 ============
class CreateInviteCodeParam(SchemaBase):
    """创建邀请码参数"""

    channel: str | None = Field(None, description='渠道(web/miniapp)')
    campaign_id: int | None = Field(None, description='活动 ID')
    max_uses: int = Field(default=0, ge=0, description='最大使用次数(0 不限)')
    reward_rule_id: int | None = Field(None, description='奖励规则 ID')


class GetInviteCodeDetail(SchemaBase):
    """邀请码详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='邀请码 ID')
    user_id: int = Field(description='持有人用户 ID')
    code: str = Field(description='邀请码')
    campaign_id: int | None = Field(None, description='活动 ID')
    channel: str | None = Field(None, description='渠道')
    max_uses: int = Field(description='最大使用次数')
    used_count: int = Field(description='已使用次数')
    reward_rule_id: int | None = Field(None, description='奖励规则 ID')
    status: int = Field(description='状态')
    created_time: datetime = Field(description='创建时间')


# ============ 邀请关系 ============
class AcceptInviteParam(SchemaBase):
    """接受邀请参数"""

    code: str = Field(min_length=1, max_length=64, description='邀请码')
    channel: str | None = Field(None, description='渠道来源')
    ip_address: str | None = Field(None, description='IP 地址')


class AcceptInviteResult(SchemaBase):
    """接受邀请结果"""

    success: bool = Field(description='是否成功')
    message: str = Field(description='提示信息')


class GetInviteRelationDetail(SchemaBase):
    """邀请关系详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='关系 ID')
    invite_code_id: int = Field(description='邀请码 ID')
    inviter_user_id: int = Field(description='邀请人用户 ID')
    invitee_user_id: int = Field(description='被邀请人用户 ID')
    inviter_reward_status: int = Field(description='邀请人奖励状态')
    invitee_reward_status: int = Field(description='被邀请人奖励状态')
    channel: str | None = Field(None, description='渠道来源')
    created_time: datetime = Field(description='创建时间')


# ============ 奖励规则 ============
class CreateRewardRuleParam(SchemaBase):
    """创建奖励规则参数"""

    name: str = Field(description='规则名称')
    inviter_reward_type: str = Field(description='邀请人权益类型(vip/points/feature)')
    inviter_reward_data: dict = Field(description='邀请人权益数据')
    invitee_reward_type: str | None = Field(None, description='被邀请人权益类型')
    invitee_reward_data: dict | None = Field(None, description='被邀请人权益数据')
    max_invites_per_user: int = Field(default=0, ge=0, description='单用户最大邀请数(0 不限)')
    valid_from: datetime | None = Field(None, description='生效时间')
    valid_to: datetime | None = Field(None, description='失效时间')


class UpdateRewardRuleParam(SchemaBase):
    """更新奖励规则参数"""

    name: str | None = Field(None, description='规则名称')
    inviter_reward_type: str | None = Field(None, description='邀请人权益类型')
    inviter_reward_data: dict | None = Field(None, description='邀请人权益数据')
    invitee_reward_type: str | None = Field(None, description='被邀请人权益类型')
    invitee_reward_data: dict | None = Field(None, description='被邀请人权益数据')
    max_invites_per_user: int | None = Field(None, ge=0, description='单用户最大邀请数')
    valid_from: datetime | None = Field(None, description='生效时间')
    valid_to: datetime | None = Field(None, description='失效时间')
    status: int | None = Field(None, ge=0, le=1, description='状态')


class GetRewardRuleDetail(SchemaBase):
    """奖励规则详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='规则 ID')
    name: str = Field(description='规则名称')
    inviter_reward_type: str = Field(description='邀请人权益类型')
    inviter_reward_data: dict = Field(description='邀请人权益数据')
    invitee_reward_type: str | None = Field(None, description='被邀请人权益类型')
    invitee_reward_data: dict | None = Field(None, description='被邀请人权益数据')
    max_invites_per_user: int = Field(description='单用户最大邀请数')
    valid_from: datetime | None = Field(None, description='生效时间')
    valid_to: datetime | None = Field(None, description='失效时间')
    status: int = Field(description='状态')
    created_time: datetime = Field(description='创建时间')
