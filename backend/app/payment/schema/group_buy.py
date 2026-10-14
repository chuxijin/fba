#!/usr/bin/env python3
from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from backend.app.payment.schema.pay import SubscriptionPrepayParam
from backend.common.schema import SchemaBase


class GroupBuyRewardParam(SchemaBase):
    template_code: str = Field(min_length=1, max_length=64)
    duration_days: int = Field(gt=0, le=36500)


class GroupBuyTierParam(SchemaBase):
    people: Literal[3, 4, 5]
    price_cents: int = Field(gt=0, le=99999999)
    member_rewards: list[GroupBuyRewardParam] = Field(min_length=1, max_length=10)
    leader_rewards: list[GroupBuyRewardParam] = Field(max_length=10)
    virtual_product_id: str | None = Field(default=None, min_length=1, max_length=128)


class GroupBuyActivityParam(SchemaBase):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default='', max_length=4000)
    template_code: str = Field(min_length=1, max_length=64)
    starts_at: datetime
    ends_at: datetime
    team_seconds: int = Field(ge=300, le=7 * 86400)
    reservation_seconds: int = Field(ge=60, le=1800)
    max_participations_per_user: int = Field(ge=1, le=100)
    reward_stack_policy: Literal['independent']
    channels: list[Literal['virtual', 'hupijiao']] = Field(min_length=1, max_length=2)
    tiers: list[GroupBuyTierParam] = Field(min_length=1, max_length=3)
    status: Literal['draft', 'active', 'disabled'] = 'draft'

    @model_validator(mode='after')
    def validate_rules(self) -> Self:
        if self.starts_at.utcoffset() is None or self.ends_at.utcoffset() is None:
            raise ValueError('活动时间必须包含时区')
        if self.starts_at >= self.ends_at:
            raise ValueError('活动开始时间必须早于结束时间')
        if self.reservation_seconds > self.team_seconds:
            raise ValueError('占位时限不能超过成团时限')
        if len({tier.people for tier in self.tiers}) != len(self.tiers):
            raise ValueError('人数档位不能重复')
        if len(set(self.channels)) != len(self.channels):
            raise ValueError('支付渠道不能重复')
        if 'virtual' in self.channels and any(not tier.virtual_product_id for tier in self.tiers):
            raise ValueError('每档虚拟支付必须配置匹配团价的道具 ID')
        return self


class GroupBuyCreateTeamParam(SchemaBase):
    activity_id: int = Field(gt=0)
    people: Literal[3, 4, 5]
    request_key: str = Field(min_length=8, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')


class GroupBuyPrepayParam(SubscriptionPrepayParam):
    # 购买项来自团快照，禁止客户端用 template_code 改价或换套餐。
    template_code: str = Field(default='', max_length=64, exclude=True)
    inviter_user_id: int | None = Field(default=None, gt=0)


class GroupBuySummary(SchemaBase):
    share_code: str
    status: Literal['draft', 'forming', 'succeeded', 'expired', 'cancelled']
    people: int
    paid_people: int
    deadline: datetime | None = None
    base_status: str = 'pending'
    reward_status: str = 'pending'


class GroupBuyTaskRetryParam(SchemaBase):
    confirmed_not_sent: bool = False
