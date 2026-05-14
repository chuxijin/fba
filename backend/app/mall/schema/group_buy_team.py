#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

# ===== enums =====
TeamStatus = Literal['pending', 'success', 'failed', 'cancelled']


# ===== member =====
class GroupBuyMemberBase(SchemaBase):
    """拼团成员基础"""

    team_id: int = Field(gt=0, description='团队 ID')
    user_id: int = Field(gt=0, description='用户 ID')
    is_leader: bool = Field(default=False, description='是否团长')
    paid_amount: Decimal = Field(ge=Decimal('0'), description='支付金额')
    inviter_user_id: int | None = Field(None, gt=0, description='邀请人用户 ID')


class GetGroupBuyMemberItem(SchemaBase):
    """拼团成员列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='成员 ID')
    team_id: int = Field(description='团队 ID')
    user_id: int = Field(description='用户 ID')
    order_id: int | None = Field(None, description='订单 ID')
    is_leader: bool = Field(description='是否团长')
    paid_amount: Decimal = Field(description='支付金额')
    join_time: datetime = Field(description='参团时间')
    inviter_user_id: int | None = Field(None, description='邀请人用户 ID')


# ===== team =====
class CreateGroupBuyTeamParam(SchemaBase):
    """创建拼团团队参数"""

    activity_id: int = Field(gt=0, description='活动 ID')
    required_people: int = Field(ge=2, description='需要人数')


class JoinGroupBuyTeamParam(SchemaBase):
    """参与拼团参数"""

    team_id: int = Field(gt=0, description='团队 ID')
    inviter_user_id: int | None = Field(None, gt=0, description='邀请人用户 ID')


class GetGroupBuyTeamListItem(SchemaBase):
    """拼团团队列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='团队 ID')
    activity_id: int = Field(description='活动 ID')
    leader_user_id: int = Field(description='团长用户 ID')
    required_people: int = Field(description='需要人数')
    current_people: int = Field(description='当前人数')
    team_price: Decimal = Field(description='拼团价格')
    status: TeamStatus = Field(description='团队状态')
    start_time: datetime = Field(description='开团时间')
    expire_time: datetime = Field(description='过期时间')
    success_time: datetime | None = Field(None, description='成团时间')
    is_mock: bool = Field(description='是否模拟成团')
    share_code: str | None = Field(None, description='分享码')
    created_time: datetime = Field(description='创建时间')


class GetGroupBuyTeamDetail(GetGroupBuyTeamListItem):
    """拼团团队详情"""

    members: list[GetGroupBuyMemberItem] = Field(default_factory=list, description='成员列表')


class GroupBuyTeamProgress(SchemaBase):
    """拼团进度"""

    team_id: int = Field(description='团队 ID')
    required_people: int = Field(description='需要人数')
    current_people: int = Field(description='当前人数')
    remaining_people: int = Field(description='还差人数')
    status: TeamStatus = Field(description='团队状态')
    expire_time: datetime = Field(description='过期时间')
    is_expired: bool = Field(description='是否已过期')


# ===== internal create schemas =====
class CreateGroupBuyTeamRecord(SchemaBase):
    """拼团团队创建记录"""

    activity_id: int = Field(description='活动 ID')
    leader_user_id: int = Field(description='团长用户 ID')
    required_people: int = Field(description='需要人数')
    current_people: int = Field(default=1, description='当前人数')
    team_price: Decimal = Field(description='拼团价格')
    status: TeamStatus = Field(default='pending', description='团队状态')
    start_time: datetime = Field(description='开团时间')
    expire_time: datetime = Field(description='过期时间')
    share_code: str | None = Field(None, description='分享码')


class CreateGroupBuyMemberRecord(SchemaBase):
    """拼团成员创建记录"""

    team_id: int = Field(description='团队 ID')
    activity_id: int = Field(description='活动 ID')
    user_id: int = Field(description='用户 ID')
    is_leader: bool = Field(default=False, description='是否团长')
    paid_amount: Decimal = Field(description='支付金额')
    join_time: datetime = Field(description='参团时间')
    inviter_user_id: int | None = Field(None, description='邀请人用户 ID')
