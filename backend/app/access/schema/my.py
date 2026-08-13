#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import Field

from backend.app.access.schema.entitlement import GetMyEntitlement
from backend.app.access.schema.subscription import GetMySubscription
from backend.common.schema import SchemaBase


class GetMyMembershipProfile(SchemaBase):
    """当前商业会员身份"""

    is_member: bool = Field(default=False, description='是否持有有效付费会员')
    is_vip: bool = Field(default=False, description='是否持有任一有效付费会员')
    is_svip: bool = Field(default=False, description='是否持有有效 SVIP 档位')
    tier_code: str = Field(default='FREE', description='主会员档位编码')
    tier_name: str = Field(default='普通用户', description='主会员档位名称')
    tier_weight: int = Field(default=0, description='主会员档位权重')
    tier_badge_color: str | None = Field(default=None, description='会员徽章主题色')
    template_code: str | None = Field(default=None, description='主订阅模板编码')
    template_name: str | None = Field(default=None, description='主订阅模板名称')
    valid_from: datetime | None = Field(default=None, description='主订阅开始时间')
    valid_to: datetime | None = Field(default=None, description='主订阅结束时间')


class GetMyDomainMembership(SchemaBase):
    """领域会员身份"""

    domain_code: str = Field(description='领域编码')
    tier_code: str = Field(description='会员档位编码')
    tier_name: str = Field(description='会员档位名称')
    tier_weight: int = Field(description='会员档位权重')
    is_paid_membership: bool = Field(description='是否属于付费会员')
    template_code: str = Field(description='订阅模板编码')
    template_name: str = Field(description='订阅模板名称')
    valid_to: datetime | None = Field(default=None, description='到期时间')


class GetMyAccessSummary(SchemaBase):
    """我的权益汇总"""

    subscriptions: list[GetMySubscription] = Field(default_factory=list, description='订阅列表')
    entitlements: list[GetMyEntitlement] = Field(default_factory=list, description='权益列表')
    membership: GetMyMembershipProfile = Field(default_factory=GetMyMembershipProfile, description='会员身份')
    domain_memberships: list[GetMyDomainMembership] = Field(default_factory=list, description='领域会员身份')
