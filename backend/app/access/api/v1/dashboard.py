#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import timedelta

import sqlalchemy as sa

from fastapi import APIRouter

from backend.app.access.model.pack import EntitlementPack
from backend.app.access.model.subscription import Subscription
from backend.app.access.model.template import SubscriptionTemplate, TemplatePack
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession
from backend.utils.timezone import timezone

router = APIRouter()


class DashboardStats:
    """Dashboard 统计结果容器"""

    def __init__(
        self,
        active_subscription_count: int = 0,
        expiring_in_7_days: int = 0,
        expiring_in_30_days: int = 0,
        pack_distribution: dict[str, int] | None = None,
        grade_distribution: dict[str, int] | None = None,
        domain_distribution: dict[str, int] | None = None,
    ):
        self.active_subscription_count = active_subscription_count
        self.expiring_in_7_days = expiring_in_7_days
        self.expiring_in_30_days = expiring_in_30_days
        self.pack_distribution = pack_distribution or {}
        self.grade_distribution = grade_distribution or {}
        self.domain_distribution = domain_distribution or {}


@router.get('/stats', summary='订阅总览统计', dependencies=[DependsJwtAuth, DependsRBAC])
async def get_dashboard_stats(db: CurrentSession) -> ResponseSchemaModel[dict]:
    """订阅总览统计"""
    now = timezone.now()
    d7 = now + timedelta(days=7)
    d30 = now + timedelta(days=30)

    # 生效订阅数
    active_count = await db.scalar(
        sa.select(sa.func.count()).select_from(Subscription).where(
            Subscription.status == 'active',
            Subscription.valid_period.contains(now),
        )
    )

    # 7 天内到期
    exp_7 = await db.scalar(
        sa.select(sa.func.count()).select_from(Subscription).where(
            Subscription.status == 'active',
            sa.func.upper(Subscription.valid_period) <= d7,
            sa.func.upper(Subscription.valid_period) > now,
        )
    )

    # 30 天内到期
    exp_30 = await db.scalar(
        sa.select(sa.func.count()).select_from(Subscription).where(
            Subscription.status == 'active',
            sa.func.upper(Subscription.valid_period) <= d30,
            sa.func.upper(Subscription.valid_period) > now,
        )
    )

    # Pack 分布: 每个 pack 有多少生效订阅
    pack_rows = (await db.execute(
        sa.select(
            EntitlementPack.name,
            sa.func.count(sa.distinct(Subscription.id)),
        )
        .select_from(Subscription)
        .join(TemplatePack, TemplatePack.template_id == Subscription.template_id)
        .join(EntitlementPack, EntitlementPack.id == TemplatePack.pack_id)
        .where(
            Subscription.status == 'active',
            Subscription.valid_period.contains(now),
        )
        .group_by(EntitlementPack.name)
    )).all()
    pack_dist = {row[0]: row[1] for row in pack_rows}

    # Grade 分布
    grade_rows = (await db.execute(
        sa.select(
            sa.cast(EntitlementPack.grade, sa.String),
            sa.func.count(sa.distinct(Subscription.id)),
        )
        .select_from(Subscription)
        .join(TemplatePack, TemplatePack.template_id == Subscription.template_id)
        .join(EntitlementPack, EntitlementPack.id == TemplatePack.pack_id)
        .where(
            Subscription.status == 'active',
            Subscription.valid_period.contains(now),
        )
        .group_by(EntitlementPack.grade)
    )).all()
    grade_dist = {row[0]: row[1] for row in grade_rows}

    # Domain 分布
    from backend.app.access.model.domain import StudyDomain

    domain_rows = (await db.execute(
        sa.select(
            StudyDomain.name,
            sa.func.count(sa.distinct(Subscription.id)),
        )
        .select_from(Subscription)
        .join(TemplatePack, TemplatePack.template_id == Subscription.template_id)
        .join(EntitlementPack, EntitlementPack.id == TemplatePack.pack_id)
        .join(StudyDomain, StudyDomain.id == EntitlementPack.domain_id)
        .where(
            Subscription.status == 'active',
            Subscription.valid_period.contains(now),
            EntitlementPack.domain_id.isnot(None),
        )
        .group_by(StudyDomain.name)
    )).all()
    domain_dist = {row[0]: row[1] for row in domain_rows}

    return response_base.success(data={
        'active_subscription_count': active_count or 0,
        'expiring_in_7_days': exp_7 or 0,
        'expiring_in_30_days': exp_30 or 0,
        'pack_distribution': pack_dist,
        'grade_distribution': grade_dist,
        'domain_distribution': domain_dist,
    })
