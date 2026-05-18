#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import SubscriptionSource, SubscriptionStatus
from backend.app.access.crud.crud_domain import study_domain_dao
from backend.app.access.crud.crud_entitlement import entitlement_dao
from backend.app.access.crud.crud_grant import direct_grant_dao
from backend.app.access.crud.crud_pack import entitlement_pack_dao, pack_item_dao
from backend.app.access.crud.crud_subscription import subscription_dao
from backend.app.access.crud.crud_template import subscription_template_dao, template_pack_dao
from backend.app.access.model.entitlement import Entitlement
from backend.app.access.model.pack import EntitlementPack
from backend.app.access.model.subscription import Subscription
from backend.app.access.model.template import SubscriptionTemplate
from backend.app.access.schema.base import TimePeriodOutput
from backend.app.access.schema.entitlement import GetMyEntitlement
from backend.app.access.schema.subscription import GetMySubscription, GetMySubscriptionLedger
from backend.app.access.service.subscription_service import subscription_service
from backend.utils.timezone import timezone


_GRADE_WEIGHTS = {
    'basic': 0,
    'standard': 1,
    'premium': 2,
    'elite': 3,
}


class MyAccessService:
    """我的权益聚合服务"""

    @staticmethod
    async def get_subscriptions(
        db: AsyncSession,
        *,
        user_id: int,
        only_active: bool = False,
    ) -> list[GetMySubscription]:
        """
        获取我的订阅列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param only_active: 是否仅当前有效
        :return:
        """
        subs = (
            await subscription_service.list_active(db=db, user_id=user_id)
            if only_active
            else await subscription_service.list_for_user(
                db=db, user_id=user_id, status=SubscriptionStatus.ACTIVE
            )
        )
        if not subs:
            return []

        context = await MyAccessService._load_subscription_context(db, subs)
        return [
            MyAccessService._build_subscription_item(sub, context)
            for sub in subs
            if sub.template_id in context['templates']
        ]

    @staticmethod
    async def get_entitlements(db: AsyncSession, *, user_id: int) -> list[GetMyEntitlement]:
        """
        获取我的可用权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        active_subs = await subscription_dao.list_active_for_user(db, user_id, timezone.now())
        entitlement_codes = await MyAccessService._get_subscription_entitlement_codes(db, active_subs)

        grants = await direct_grant_dao.list_active_for_user(db, user_id=user_id, ts=timezone.now())
        entitlement_codes.update(grant.entitlement_code for grant in grants)
        if not entitlement_codes:
            return []

        entitlements = await entitlement_dao.get_by_codes(db, sorted(entitlement_codes))
        entitlement_map = {item.code: item for item in entitlements}
        return [
            MyAccessService._build_entitlement_item(entitlement_map[code])
            for code in sorted(entitlement_codes)
            if code in entitlement_map
        ]

    @staticmethod
    async def get_subscription_ledger(
        db: AsyncSession,
        *,
        user_id: int,
        limit: int = 50,
    ) -> list[GetMySubscriptionLedger]:
        """
        获取我的订阅流水

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param limit: 数量上限
        :return:
        """
        subs = await subscription_dao.list_for_user(db, user_id)
        if not subs:
            return []

        limited_subs = list(subs[:limit])
        template_ids = list({sub.template_id for sub in limited_subs})
        templates = await subscription_template_dao.select_models(db, id__in=template_ids)
        template_map = {template.id: template for template in templates}

        items: list[GetMySubscriptionLedger] = []
        for sub in limited_subs:
            template = template_map.get(sub.template_id)
            if template is None:
                continue
            items.append(
                GetMySubscriptionLedger(
                    id=sub.id,
                    template_code=template.code,
                    template_name=template.name,
                    op_type=MyAccessService._subscription_op_type(sub),
                    days=MyAccessService._subscription_days(sub),
                    source=MyAccessService._source_value(sub.source),
                    valid_to_after=sub.valid_period.upper,
                    created_time=sub.created_time,
                )
            )
        return items

    @staticmethod
    async def _load_subscription_context(
        db: AsyncSession,
        subs: Sequence[Subscription],
    ) -> dict[str, dict]:
        """
        加载订阅关联上下文

        :param db: 数据库会话
        :param subs: 订阅列表
        :return:
        """
        template_ids = list({sub.template_id for sub in subs})
        templates = await subscription_template_dao.select_models(db, id__in=template_ids)
        relations = await template_pack_dao.get_by_templates(db, template_ids)
        pack_ids = list({relation.pack_id for relation in relations})
        packs = await entitlement_pack_dao.select_models(db, id__in=pack_ids)

        domain_ids = list({pack.domain_id for pack in packs if pack.domain_id is not None})
        domains = await study_domain_dao.select_models(db, id__in=domain_ids) if domain_ids else []

        template_pack_ids: dict[int, list[int]] = {}
        for relation in relations:
            template_pack_ids.setdefault(relation.template_id, []).append(relation.pack_id)

        return {
            'templates': {template.id: template for template in templates},
            'packs': {pack.id: pack for pack in packs},
            'domains': {domain.id: domain for domain in domains},
            'template_pack_ids': template_pack_ids,
        }

    @staticmethod
    async def _get_subscription_entitlement_codes(
        db: AsyncSession,
        subs: Sequence[Subscription],
    ) -> set[str]:
        """
        获取订阅包含的权益编码

        :param db: 数据库会话
        :param subs: 订阅列表
        :return:
        """
        if not subs:
            return set()

        template_ids = list({sub.template_id for sub in subs})
        relations = await template_pack_dao.get_by_templates(db, template_ids)
        pack_ids = list({relation.pack_id for relation in relations})
        pack_items = await pack_item_dao.get_by_packs(db, pack_ids)
        entitlement_ids = list({item.entitlement_id for item in pack_items})
        if not entitlement_ids:
            return set()

        entitlements = await entitlement_dao.select_models(db, id__in=entitlement_ids)
        return {entitlement.code for entitlement in entitlements}

    @staticmethod
    def _build_subscription_item(sub: Subscription, context: dict[str, dict]) -> GetMySubscription:
        """
        构建我的订阅项

        :param sub: 订阅
        :param context: 关联上下文
        :return:
        """
        template = context['templates'][sub.template_id]
        packs = MyAccessService._subscription_packs(sub.template_id, context)
        primary_pack = MyAccessService._primary_pack(packs)
        valid_period = TimePeriodOutput.from_range(sub.valid_period)

        return GetMySubscription(
            id=sub.id,
            template_code=template.code,
            template_name=template.name,
            pack_code=primary_pack.code if primary_pack else None,
            grade=MyAccessService._pack_grade(primary_pack),
            domain_codes=MyAccessService._domain_codes(packs, context),
            cover_image=template.cover_image,
            valid_period=valid_period,
            valid_from=sub.valid_period.lower,
            valid_to=sub.valid_period.upper,
            status=sub.status,
            created_time=sub.created_time,
        )

    @staticmethod
    def _build_entitlement_item(entitlement: Entitlement) -> GetMyEntitlement:
        """
        构建我的权益项

        :param entitlement: 权益
        :return:
        """
        return GetMyEntitlement(
            code=entitlement.code,
            name=entitlement.name,
            category=entitlement.category,
            description=entitlement.description,
        )

    @staticmethod
    def _subscription_packs(template_id: int, context: dict[str, dict]) -> list[EntitlementPack]:
        """
        获取订阅关联权益包

        :param template_id: 模板 ID
        :param context: 关联上下文
        :return:
        """
        pack_ids = context['template_pack_ids'].get(template_id, [])
        return [context['packs'][pack_id] for pack_id in pack_ids if pack_id in context['packs']]

    @staticmethod
    def _primary_pack(packs: Sequence[EntitlementPack]) -> EntitlementPack | None:
        """
        获取主权益包

        :param packs: 权益包列表
        :return:
        """
        if not packs:
            return None
        return sorted(
            packs,
            key=lambda pack: _GRADE_WEIGHTS.get(MyAccessService._source_value(pack.grade), 0),
            reverse=True,
        )[0]

    @staticmethod
    def _domain_codes(packs: Sequence[EntitlementPack], context: dict[str, dict]) -> list[str]:
        """
        获取领域编码

        :param packs: 权益包列表
        :param context: 关联上下文
        :return:
        """
        codes: list[str] = []
        for pack in packs:
            if pack.domain_id is None:
                continue
            domain = context['domains'].get(pack.domain_id)
            if domain is None or domain.code in codes:
                continue
            codes.append(domain.code)
        return codes

    @staticmethod
    def _pack_grade(pack: EntitlementPack | None) -> str:
        """
        获取权益包档次

        :param pack: 权益包
        :return:
        """
        if pack is None:
            return 'basic'
        return MyAccessService._source_value(pack.grade)

    @staticmethod
    def _source_value(source: object) -> str:
        """
        获取枚举值

        :param source: 枚举或字符串
        :return:
        """
        return str(getattr(source, 'value', source))

    @staticmethod
    def _subscription_op_type(sub: Subscription) -> str:
        """
        获取订阅流水操作类型

        :param sub: 订阅
        :return:
        """
        if sub.status == SubscriptionStatus.CANCELLED:
            return 'revoke'
        if sub.status == SubscriptionStatus.REFUNDED:
            return 'refund'
        if sub.status == SubscriptionStatus.EXPIRED:
            return 'expire'
        if sub.parent_subscription_id is not None:
            return 'extend'
        if sub.source == SubscriptionSource.ORDER:
            return 'grant'
        return 'grant'

    @staticmethod
    def _subscription_days(sub: Subscription) -> int:
        """
        获取订阅天数

        :param sub: 订阅
        :return:
        """
        valid_from: datetime | None = sub.valid_period.lower
        valid_to: datetime | None = sub.valid_period.upper
        if valid_from is None or valid_to is None:
            return 0
        return max((valid_to - valid_from).days, 0)


my_access_service: MyAccessService = MyAccessService()
