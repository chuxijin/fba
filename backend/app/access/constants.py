#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import Enum


class CommonStatus(str, Enum):
    """通用状态"""

    ACTIVE = 'active'
    ARCHIVED = 'archived'
    DRAFT = 'draft'


class EntitlementCategory(str, Enum):
    """权益分类"""

    ACCESS = 'access'
    QUOTA = 'quota'
    BOOST = 'boost'
    FEATURE = 'feature'


class EntitlementMetric(str, Enum):
    """权益度量"""

    BOOLEAN = 'boolean'
    COUNT = 'count'
    LEVEL = 'level'


class EntitlementVerb(str, Enum):
    """权益动作"""

    ACCESS = 'access'
    VIEW = 'view'
    EXPORT = 'export'
    DOWNLOAD = 'download'
    SHARE = 'share'
    COMMENT = 'comment'


class GradeLevel(str, Enum):
    """档次等级"""

    BASIC = 'basic'
    STANDARD = 'standard'
    PREMIUM = 'premium'
    ELITE = 'elite'


class TemplateKind(str, Enum):
    """订阅模板类型"""

    STANDARD = 'standard'
    BUNDLE = 'bundle'
    TRIAL = 'trial'
    GIFT = 'gift'
    CORPORATE = 'corporate'


class SubscriptionStatus(str, Enum):
    """订阅状态"""

    ACTIVE = 'active'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'


class SubscriptionSource(str, Enum):
    """订阅来源"""

    ORDER = 'order'
    ACTCODE = 'actcode'
    QUEST = 'quest'
    GIFT = 'gift'
    ADMIN = 'admin'
    MIGRATION = 'migration'


class LedgerOperation(str, Enum):
    """账本操作类型"""

    CREDIT = 'credit'
    DEBIT = 'debit'
    RESET = 'reset'
    REFUND = 'refund'
    ADJUST = 'adjust'


class GrantMode(str, Enum):
    """资源规则授权模式"""

    ACCESS = 'access'
    TRIAL = 'trial'
    FREE_PASS = 'free_pass'
    OWNERSHIP_REQUIRED = 'ownership_required'


class GrantSource(str, Enum):
    """直接授予来源"""

    ADMIN = 'admin'
    COMPENSATION = 'compensation'
    PROMO = 'promo'
    QUEST = 'quest'
    INVITE = 'invite'


class DecisionKind(str, Enum):
    """决策结果"""

    ALLOW = 'allow'
    DENY = 'deny'


class CycleType(str, Enum):
    """配额周期类型"""

    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    YEARLY = 'yearly'
    LIFETIME = 'lifetime'


class ResourceType(str, Enum):
    """资源类型常量(用于 resource_rule.resource_type)"""

    QBANK = 'qbank'
    CONTENT = 'content'
    VIDEO = 'video'
    LIVE = 'live'
    CATEGORY = 'category'
    AGENT_SHENLUN = 'agent_shenlun'


class ReasonCode(str, Enum):
    """决策原因码"""

    FREE_RESOURCE = 'free_resource'
    FREE_PASS = 'free_pass'
    OWNERSHIP = 'ownership'
    SUBSCRIPTION_ACCESS = 'subscription_access'
    DIRECT_GRANT = 'direct_grant'
    QUOTA_TRIAL = 'quota_trial'
    QUOTA_EXHAUSTED = 'quota_exhausted'
    NO_MATCHING_GRANT = 'no_matching_grant'
    AUDIENCE_NOT_MATCH = 'audience_not_match'
