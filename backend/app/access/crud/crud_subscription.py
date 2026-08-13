#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Integer, Row, Select, false, func, literal, select, union_all
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import CommonStatus, SubscriptionSource, SubscriptionStatus
from backend.app.access.model.subscription import Subscription
from backend.utils.timezone import timezone


class CRUDSubscription(CRUDPlus[Subscription]):
    """用户订阅 CRUD"""

    async def list_active_for_user(
        self,
        db: AsyncSession,
        user_id: int,
        ts: datetime,
    ) -> Sequence[Subscription]:
        """
        列出用户在指定时刻有效的订阅

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param ts: 时间点
        :return:
        """
        stmt = select(self.model).where(
            self.model.user_id == user_id,
            self.model.status == SubscriptionStatus.ACTIVE,
            self.model.valid_period.contains(ts),
        )
        return (await db.execute(stmt)).scalars().all()

    async def list_for_user(
        self,
        db: AsyncSession,
        user_id: int,
        *,
        status: SubscriptionStatus | None = None,
    ) -> Sequence[Subscription]:
        """
        列出用户的所有订阅

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param status: 状态过滤
        :return:
        """
        stmt = select(self.model).where(self.model.user_id == user_id)
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        stmt = stmt.order_by(self.model.id.desc())
        return (await db.execute(stmt)).scalars().all()

    async def list_my_subscription_rows(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        only_active: bool,
        ts: datetime,
    ) -> Sequence[Row]:
        """
        获取我的订阅展示行

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param only_active: 是否仅当前有效
        :param ts: 时间点
        :return:
        """
        from backend.app.access.model.domain import StudyDomain
        from backend.app.access.model.pack import EntitlementPack
        from backend.app.access.model.template import SubscriptionTemplate, TemplatePack
        from backend.app.access.model.tier import MembershipTier

        stmt = (
            select(
                self.model.id.label('subscription_id'),
                self.model.template_id.label('template_id'),
                self.model.valid_period.label('valid_period'),
                self.model.status.label('status'),
                self.model.created_time.label('created_time'),
                SubscriptionTemplate.code.label('template_code'),
                SubscriptionTemplate.name.label('template_name'),
                SubscriptionTemplate.cover_image.label('cover_image'),
                SubscriptionTemplate.metadata_.label('template_metadata'),
                MembershipTier.code.label('tier_code'),
                MembershipTier.name.label('tier_name'),
                func.coalesce(MembershipTier.weight, 0).label('tier_weight'),
                func.coalesce(MembershipTier.is_paid, false()).label('tier_is_paid'),
                MembershipTier.badge_color.label('tier_badge_color'),
                EntitlementPack.id.label('pack_id'),
                EntitlementPack.code.label('pack_code'),
                StudyDomain.code.label('domain_code'),
            )
            .join(SubscriptionTemplate, SubscriptionTemplate.id == self.model.template_id)
            .outerjoin(MembershipTier, MembershipTier.id == SubscriptionTemplate.tier_id)
            .outerjoin(TemplatePack, TemplatePack.template_id == self.model.template_id)
            .outerjoin(EntitlementPack, EntitlementPack.id == TemplatePack.pack_id)
            .outerjoin(StudyDomain, StudyDomain.id == EntitlementPack.domain_id)
            .where(
                self.model.user_id == user_id,
                self.model.status == SubscriptionStatus.ACTIVE,
            )
            .order_by(self.model.id.desc(), TemplatePack.id.asc())
        )
        if only_active:
            stmt = stmt.where(self.model.valid_period.contains(ts))
        return (await db.execute(stmt)).all()

    async def list_my_access_graph_rows(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        ts: datetime,
    ) -> Sequence[Row]:
        """
        获取我的订阅与订阅权益聚合行

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param ts: 时间点
        :return:
        """
        from backend.app.access.model.domain import StudyDomain
        from backend.app.access.model.entitlement import Entitlement
        from backend.app.access.model.pack import EntitlementPack, PackItem
        from backend.app.access.model.template import SubscriptionTemplate, TemplatePack

        stmt = (
            select(
                self.model.id.label('subscription_id'),
                self.model.template_id.label('template_id'),
                self.model.valid_period.label('valid_period'),
                self.model.status.label('status'),
                self.model.created_time.label('created_time'),
                SubscriptionTemplate.code.label('template_code'),
                SubscriptionTemplate.name.label('template_name'),
                SubscriptionTemplate.cover_image.label('cover_image'),
                EntitlementPack.id.label('pack_id'),
                EntitlementPack.code.label('pack_code'),
                StudyDomain.code.label('domain_code'),
                PackItem.value_int.label('value_int'),
                PackItem.value_meta.label('value_meta'),
                Entitlement.id.label('entitlement_id'),
                Entitlement.code.label('entitlement_code'),
                Entitlement.name.label('entitlement_name'),
                Entitlement.category.label('entitlement_category'),
                Entitlement.description.label('entitlement_description'),
            )
            .select_from(self.model)
            .join(SubscriptionTemplate, SubscriptionTemplate.id == self.model.template_id)
            .outerjoin(TemplatePack, TemplatePack.template_id == self.model.template_id)
            .outerjoin(EntitlementPack, EntitlementPack.id == TemplatePack.pack_id)
            .outerjoin(StudyDomain, StudyDomain.id == EntitlementPack.domain_id)
            .outerjoin(
                PackItem,
                (PackItem.pack_id == EntitlementPack.id) & (PackItem.status == CommonStatus.ACTIVE),
            )
            .outerjoin(Entitlement, Entitlement.id == PackItem.entitlement_id)
            .where(
                self.model.user_id == user_id,
                self.model.status == SubscriptionStatus.ACTIVE,
                self.model.valid_period.contains(ts),
            )
            .order_by(self.model.id.desc(), TemplatePack.id.asc(), PackItem.id.asc())
        )
        return (await db.execute(stmt)).all()

    async def has_active_paid_membership(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        ts: datetime,
    ) -> bool:
        """判断用户是否持有当前有效的付费会员订阅"""
        from backend.app.access.model.template import SubscriptionTemplate
        from backend.app.access.model.tier import MembershipTier

        stmt = (
            select(literal(True))
            .select_from(self.model)
            .join(SubscriptionTemplate, SubscriptionTemplate.id == self.model.template_id)
            .join(MembershipTier, MembershipTier.id == SubscriptionTemplate.tier_id)
            .where(
                self.model.user_id == user_id,
                self.model.status == SubscriptionStatus.ACTIVE,
                self.model.valid_period.contains(ts),
                MembershipTier.status == CommonStatus.ACTIVE,
                MembershipTier.is_paid.is_(True),
            )
            .limit(1)
        )
        return bool((await db.execute(stmt)).scalar_one_or_none())

    async def list_my_access_entitlement_rows(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        ts: datetime,
    ) -> Sequence[Row]:
        """
        获取我的有效权益聚合行

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param ts: 时间点
        :return:
        """
        from backend.app.access.model.entitlement import Entitlement
        from backend.app.access.model.grant import DirectGrant
        from backend.app.access.model.pack import PackItem
        from backend.app.access.model.template import TemplatePack

        subscription_stmt = (
            select(
                Entitlement.code.label('entitlement_code'),
                Entitlement.name.label('entitlement_name'),
                Entitlement.category.label('entitlement_category'),
                Entitlement.description.label('entitlement_description'),
                PackItem.value_int.label('value_int'),
                PackItem.value_meta.label('value_meta'),
                literal('subscription').label('row_source'),
            )
            .select_from(self.model)
            .join(TemplatePack, TemplatePack.template_id == self.model.template_id)
            .join(
                PackItem,
                (PackItem.pack_id == TemplatePack.pack_id) & (PackItem.status == CommonStatus.ACTIVE),
            )
            .join(Entitlement, Entitlement.id == PackItem.entitlement_id)
            .where(
                self.model.user_id == user_id,
                self.model.status == SubscriptionStatus.ACTIVE,
                self.model.valid_period.contains(ts),
            )
            .distinct()
        )
        direct_grant_stmt = (
            select(
                Entitlement.code.label('entitlement_code'),
                Entitlement.name.label('entitlement_name'),
                Entitlement.category.label('entitlement_category'),
                Entitlement.description.label('entitlement_description'),
                literal(None, type_=Integer).label('value_int'),
                literal(None, type_=JSONB).label('value_meta'),
                literal('direct_grant').label('row_source'),
            )
            .select_from(DirectGrant)
            .join(Entitlement, Entitlement.code == DirectGrant.entitlement_code)
            .where(
                DirectGrant.user_id == user_id,
                DirectGrant.status == CommonStatus.ACTIVE,
                DirectGrant.valid_period.contains(ts),
            )
            .distinct()
        )
        entitlement_rows = union_all(subscription_stmt, direct_grant_stmt).subquery()
        stmt = select(entitlement_rows).order_by(entitlement_rows.c.entitlement_code.asc())
        return (await db.execute(stmt)).all()

    async def list_active_entitlement_rows_for_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        ts: datetime,
    ) -> Sequence[Row]:
        """
        获取用户有效订阅权益行

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param ts: 时间点
        :return:
        """
        from backend.app.access.model.entitlement import Entitlement
        from backend.app.access.model.pack import PackItem
        from backend.app.access.model.template import TemplatePack

        stmt = (
            select(
                Entitlement.id.label('entitlement_id'),
                Entitlement.code.label('entitlement_code'),
                Entitlement.name.label('entitlement_name'),
                Entitlement.category.label('entitlement_category'),
                Entitlement.description.label('entitlement_description'),
                PackItem.value_int.label('value_int'),
                PackItem.value_meta.label('value_meta'),
            )
            .select_from(self.model)
            .join(TemplatePack, TemplatePack.template_id == self.model.template_id)
            .join(PackItem, PackItem.pack_id == TemplatePack.pack_id)
            .join(Entitlement, Entitlement.id == PackItem.entitlement_id)
            .where(
                self.model.user_id == user_id,
                self.model.status == SubscriptionStatus.ACTIVE,
                self.model.valid_period.contains(ts),
                PackItem.status == CommonStatus.ACTIVE,
            )
            .order_by(Entitlement.code.asc(), PackItem.id.asc())
        )
        return (await db.execute(stmt)).all()

    async def get_select(
        self,
        *,
        user_id: int | None = None,
        template_id: int | None = None,
        status: SubscriptionStatus | None = None,
        source: SubscriptionSource | None = None,
    ) -> Select:
        """
        分页查询语句 (联表查询，带关联信息)

        :param user_id: 用户 ID
        :param template_id: 模板 ID
        :param status: 状态
        :param source: 来源
        :return:
        """
        from backend.app.access.model.template import SubscriptionTemplate
        from backend.app.access.model.tier import MembershipTier
        from backend.app.admin.model.user import User
        stmt = (
            select(
                Subscription.id,
                Subscription.user_id,
                Subscription.template_id,
                Subscription.valid_period,
                Subscription.status,
                Subscription.source,
                Subscription.source_ref,
                Subscription.parent_subscription_id,
                Subscription.cancel_reason,
                Subscription.created_time,
                Subscription.updated_time,
                User.username.label('username'),
                User.nickname.label('nickname'),
                SubscriptionTemplate.code.label('template_code'),
                SubscriptionTemplate.name.label('template_name'),
                MembershipTier.code.label('tier_code'),
                MembershipTier.name.label('tier_name'),
                func.coalesce(MembershipTier.weight, 0).label('tier_weight'),
                func.coalesce(MembershipTier.is_paid, false()).label('is_paid_membership'),
                func.lower(Subscription.valid_period).label('valid_from'),
                func.upper(Subscription.valid_period).label('valid_to'),
            )
            .outerjoin(User, Subscription.user_id == User.id)
            .outerjoin(SubscriptionTemplate, Subscription.template_id == SubscriptionTemplate.id)
            .outerjoin(MembershipTier, MembershipTier.id == SubscriptionTemplate.tier_id)
            .order_by(Subscription.id.desc())
        )

        if user_id is not None:
            stmt = stmt.where(Subscription.user_id == user_id)
        if template_id is not None:
            stmt = stmt.where(Subscription.template_id == template_id)
        if status is not None:
            stmt = stmt.where(Subscription.status == status)
        if source is not None:
            stmt = stmt.where(Subscription.source == source)

        return stmt

    async def get_detail(
        self,
        db: AsyncSession,
        pk: int,
    ) -> Row | None:
        """
        获取订阅详情 (带关联的用户名、模板和生效到期时间)

        :param db: 数据库会话
        :param pk: 订阅 ID
        :return:
        """
        from backend.app.access.model.template import SubscriptionTemplate
        from backend.app.access.model.tier import MembershipTier
        from backend.app.admin.model.user import User
        stmt = (
            select(
                Subscription.id,
                Subscription.user_id,
                Subscription.template_id,
                Subscription.valid_period,
                Subscription.status,
                Subscription.source,
                Subscription.source_ref,
                Subscription.parent_subscription_id,
                Subscription.cancel_reason,
                Subscription.created_time,
                Subscription.updated_time,
                User.username.label('username'),
                User.nickname.label('nickname'),
                SubscriptionTemplate.code.label('template_code'),
                SubscriptionTemplate.name.label('template_name'),
                MembershipTier.code.label('tier_code'),
                MembershipTier.name.label('tier_name'),
                func.coalesce(MembershipTier.weight, 0).label('tier_weight'),
                func.coalesce(MembershipTier.is_paid, false()).label('is_paid_membership'),
                func.lower(Subscription.valid_period).label('valid_from'),
                func.upper(Subscription.valid_period).label('valid_to'),
            )
            .outerjoin(User, Subscription.user_id == User.id)
            .outerjoin(SubscriptionTemplate, Subscription.template_id == SubscriptionTemplate.id)
            .outerjoin(MembershipTier, MembershipTier.id == SubscriptionTemplate.tier_id)
            .where(Subscription.id == pk)
        )
        return (await db.execute(stmt)).first()

    async def expire_due(self, db: AsyncSession) -> int:
        """
        批量将已过期的 active 订阅标记为 expired

        :param db: 数据库会话
        :return: 受影响的行数
        """
        from sqlalchemy import func, update

        now = timezone.now()
        stmt = (
            update(self.model)
            .where(
                self.model.status == SubscriptionStatus.ACTIVE,
                func.upper(self.model.valid_period) <= now,
            )
            .values(status=SubscriptionStatus.EXPIRED)
        )
        result = await db.execute(stmt)
        return result.rowcount


subscription_dao: CRUDSubscription = CRUDSubscription(Subscription)
