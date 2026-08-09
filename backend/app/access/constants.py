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


class QuotaGrantSource(str, Enum):
    """额度包来源

    额度包是配额的唯一真相源, 订阅周期补账与运营发放共用同一张表,
    因此免费用户也可以在没有任何订阅的情况下持有额度。
    """

    SUBSCRIPTION = 'subscription'
    PURCHASE = 'purchase'
    ACTIVITY = 'activity'
    INVITE = 'invite'
    QUEST = 'quest'
    EXCHANGE = 'exchange'
    COMPENSATION = 'compensation'
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
    """资源规则授权模式

    ACCESS    布尔准入, 持有 entitlement_code 即放行
    METERED   计量配额, 需有额度包余额并扣减
    FREE_PASS 限免时段, 对所有人放行

    试看不在此枚举内 —— 它是规则上的降级策略(trial_policy), 不是一种权益。
    """

    ACCESS = 'access'
    METERED = 'metered'
    FREE_PASS = 'free_pass'


class TrialMode(str, Enum):
    """试看策略模式(resource_rule.trial_policy.mode)

    ORDINAL     按序位: 子资源序号小于 limit 时放行(如前 5 道题)
    FRACTION    按比例: 子资源序号小于 total * ratio 时放行(如前 10%)
    EXCERPT     按摘录: 放行但要求业务层截断到 chars 字(如前 300 字)
    DAILY_COUNT 按日计数: 每日放行 limit 次, 走匿名计数器不发权益凭证
    """

    ORDINAL = 'ordinal'
    FRACTION = 'fraction'
    EXCERPT = 'excerpt'
    DAILY_COUNT = 'daily_count'


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
    QBANK_COLLECTION = 'qbank_collection'
    CONTENT = 'content'
    VIDEO = 'video'
    LIVE = 'live'
    CATEGORY = 'category'
    AGENT_SHENLUN = 'agent_shenlun'
    AGENT_GRADING = 'agents.grading'
    RENDER_BOOK = 'render_book'


class ReasonCode(str, Enum):
    """决策原因码"""

    FREE_RESOURCE = 'free_resource'
    FREE_PASS = 'free_pass'
    #: 资源归属者本人(如题库作者访问自己的题库), 非单点买断
    OWNERSHIP = 'ownership'
    SUBSCRIPTION_ACCESS = 'subscription_access'
    DIRECT_GRANT = 'direct_grant'
    METERED_CONSUMED = 'metered_consumed'
    QUOTA_EXHAUSTED = 'quota_exhausted'
    TRIAL_POLICY = 'trial_policy'
    TRIAL_EXHAUSTED = 'trial_exhausted'
    NO_MATCHING_GRANT = 'no_matching_grant'
    AUDIENCE_NOT_MATCH = 'audience_not_match'
