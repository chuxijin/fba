#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import Row

from backend.app.access.constants import (
    EntitlementCategory,
    SubscriptionSource,
    SubscriptionStatus,
)
from backend.app.access.crud.crud_domain import study_domain_dao
from backend.app.access.crud.crud_entitlement import entitlement_dao
from backend.app.access.crud.crud_grant import direct_grant_dao
from backend.app.access.crud.crud_pack import entitlement_pack_dao, pack_item_dao
from backend.app.access.crud.crud_subscription import subscription_dao
from backend.app.access.crud.crud_template import subscription_template_dao, template_pack_dao
from backend.app.access.model.entitlement import Entitlement
from backend.app.access.model.pack import EntitlementPack
from backend.app.access.model.subscription import Subscription
from backend.app.access.schema.base import TimePeriodOutput
from backend.app.access.schema.entitlement import GetMyEntitlement
from backend.app.access.schema.my import GetMyAccessSummary
from backend.app.access.schema.subscription import GetMySubscription, GetMySubscriptionLedger
from backend.common.cache.redis_cache import RedisCache
from backend.common.cache.serializers import PydanticSerializer
from backend.utils.timezone import timezone


_MY_ACCESS_SUMMARY_CACHE_TTL = 30


my_summary_cache: RedisCache[GetMyAccessSummary] = RedisCache(
    prefix='access:my:summary',
    ttl=_MY_ACCESS_SUMMARY_CACHE_TTL,
    serializer=PydanticSerializer(GetMyAccessSummary),
)

class MyAccessService:
    """我的权益聚合服务"""

    @staticmethod
    async def invalidate_summary_cache(user_id: int) -> None:
        """
        删除我的权益汇总缓存(同时联动失效 snapshot 缓存)

        :param user_id: 用户 ID
        :return:
        """
        from backend.app.access.engine.snapshot import snapshot_service

        await my_summary_cache.invalidate(user_id)
        await snapshot_service.invalidate_cache(user_id)

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
        rows = await subscription_dao.list_my_subscription_rows(
            db,
            user_id=user_id,
            only_active=only_active,
            ts=timezone.now(),
        )
        if not rows:
            return []

        return MyAccessService._build_subscription_items_from_rows(rows)

    @staticmethod
    async def get_entitlements(db: AsyncSession, *, user_id: int) -> list[GetMyEntitlement]:
        """
        获取我的可用权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        now = timezone.now()

        subscription_rows = await subscription_dao.list_active_entitlement_rows_for_user(
            db,
            user_id=user_id,
            ts=now,
        )

        entitlement_map: dict[str, dict[str, Any]] = {}
        pack_items: list[dict[str, Any]] = []
        for row in subscription_rows:
            code = str(row.entitlement_code)
            entitlement_map.setdefault(
                code,
                {
                    'code': code,
                    'name': row.entitlement_name,
                    'category': row.entitlement_category,
                    'description': row.entitlement_description,
                },
            )
            pack_items.append({
                'entitlement_code': code,
                'value_int': row.value_int,
                'value_meta': row.value_meta or {},
            })

        grant_rows = await direct_grant_dao.list_active_entitlement_rows_for_user(
            db,
            user_id=user_id,
            ts=now,
        )
        for row in grant_rows:
            code = str(row.entitlement_code)
            entitlement_map.setdefault(
                code,
                {
                    'code': code,
                    'name': row.entitlement_name,
                    'category': row.entitlement_category,
                    'description': row.entitlement_description,
                },
            )

        if not entitlement_map:
            return []

        # 聚合 QUOTA 类型权益的当前余额: 优先取额度包余额, 否则按 pack_item 配置回退
        quota_codes = [
            code
            for code, entitlement in entitlement_map.items()
            if entitlement['category'] == EntitlementCategory.QUOTA
        ]
        balances = await MyAccessService._load_quota_balances(
            db,
            user_id=user_id,
            now=now,
            pack_items=pack_items,
            quota_codes=quota_codes,
        )

        return [
            GetMyEntitlement(
                code=entitlement['code'],
                name=entitlement['name'],
                category=entitlement['category'],
                description=entitlement['description'],
                balance=balances.get(code),
            )
            for code, entitlement in sorted(entitlement_map.items())
        ]

    @staticmethod
    async def _build_entitlements_from_rows(
        db: AsyncSession,
        *,
        user_id: int,
        now: datetime,
        subscription_rows: Sequence[Row],
        include_direct_grants: bool = True,
    ) -> list[GetMyEntitlement]:
        """
        从订阅权益聚合行构建权益列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param now: 当前时间
        :param subscription_rows: 订阅权益聚合行
        :param include_direct_grants: 是否补查直接授予
        :return:
        """
        entitlement_map: dict[str, dict[str, Any]] = {}
        pack_items: list[dict[str, Any]] = []
        for row in subscription_rows:
            if not row.entitlement_code:
                continue

            code = str(row.entitlement_code)
            entitlement_map.setdefault(
                code,
                {
                    'code': code,
                    'name': row.entitlement_name,
                    'category': row.entitlement_category,
                    'description': row.entitlement_description,
                },
            )
            row_source = getattr(row, 'row_source', 'subscription')
            if row_source != 'direct_grant':
                pack_items.append({
                    'entitlement_code': code,
                    'value_int': row.value_int,
                    'value_meta': row.value_meta or {},
                })

        if include_direct_grants:
            grant_rows = await direct_grant_dao.list_active_entitlement_rows_for_user(
                db,
                user_id=user_id,
                ts=now,
            )
            for row in grant_rows:
                code = str(row.entitlement_code)
                entitlement_map.setdefault(
                    code,
                    {
                        'code': code,
                        'name': row.entitlement_name,
                        'category': row.entitlement_category,
                        'description': row.entitlement_description,
                    },
                )

        if not entitlement_map:
            return []

        quota_codes = [
            code
            for code, entitlement in entitlement_map.items()
            if entitlement['category'] == EntitlementCategory.QUOTA
        ]
        balances = await MyAccessService._load_quota_balances(
            db,
            user_id=user_id,
            now=now,
            pack_items=pack_items,
            quota_codes=quota_codes,
        )

        return [
            GetMyEntitlement(
                code=entitlement['code'],
                name=entitlement['name'],
                category=entitlement['category'],
                description=entitlement['description'],
                balance=balances.get(code),
            )
            for code, entitlement in sorted(entitlement_map.items())
        ]

    @staticmethod
    async def get_summary(
        db: AsyncSession,
        *,
        user_id: int,
        force_refresh: bool = False,
    ) -> GetMyAccessSummary:
        """
        获取我的权益汇总

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param force_refresh: 是否强制刷新
        :return:
        """
        if force_refresh:
            await my_summary_cache.invalidate(user_id)

        async def factory() -> GetMyAccessSummary:
            now = timezone.now()

            subscription_rows = await subscription_dao.list_my_subscription_rows(
                db,
                user_id=user_id,
                only_active=True,
                ts=now,
            )
            entitlement_rows = await subscription_dao.list_my_access_entitlement_rows(
                db,
                user_id=user_id,
                ts=now,
            )

            subscriptions = MyAccessService._build_subscription_items_from_rows(subscription_rows)
            entitlements = await MyAccessService._build_entitlements_from_rows(
                db,
                user_id=user_id,
                now=now,
                subscription_rows=entitlement_rows,
                include_direct_grants=False,
            )
            return GetMyAccessSummary(
                subscriptions=subscriptions,
                entitlements=entitlements,
            )

        result = await my_summary_cache.get_or_set(user_id, factory=factory)
        return result if result is not None else GetMyAccessSummary(subscriptions=[], entitlements=[])

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
    async def _get_subscription_entitlement_context(
        db: AsyncSession,
        subs: Sequence[Subscription],
    ) -> dict[str, object]:
        """
        获取订阅权益上下文

        :param db: 数据库会话
        :param subs: 订阅列表
        :return:
        """
        if not subs:
            return {
                'entitlement_codes': set(),
                'pack_items': [],
                'entitlement_map': {},
            }

        template_ids = list({sub.template_id for sub in subs})
        relations = await template_pack_dao.get_by_templates(db, template_ids)

        pack_ids = list({relation.pack_id for relation in relations})
        pack_items = await pack_item_dao.get_by_packs(db, pack_ids)

        entitlement_ids = list({item.entitlement_id for item in pack_items})
        if not entitlement_ids:
            return {
                'entitlement_codes': set(),
                'pack_items': [],
                'entitlement_map': {},
            }

        entitlements = await entitlement_dao.select_models(db, id__in=entitlement_ids)

        entitlement_map = {entitlement.id: entitlement for entitlement in entitlements}
        entitlement_codes = {entitlement.code for entitlement in entitlements}
        return {
            'entitlement_codes': entitlement_codes,
            'pack_items': list(pack_items),
            'entitlement_map': entitlement_map,
        }


    @staticmethod
    async def _get_quota_scope_keys_from_rules(
        db: AsyncSession,
        quota_codes: list[str],
    ) -> dict[str, str]:
        """
        从 resource_rule 与资源档案解析配额范围键

        :param db: 数据库会话
        :param quota_codes: 配额权益编码
        :return:
        """
        from sqlalchemy import select as sa_select

        import backend.app.access.service.resource_profiles  # noqa: F401

        from backend.app.access.model.rule import ResourceRule
        from backend.app.access.service.resource_profile_registry import access_profile_registry

        stmt = sa_select(ResourceRule).where(
            ResourceRule.entitlement_code.in_(quota_codes),
            ResourceRule.status == 'active',
        )
        rules = (await db.execute(stmt)).scalars().all()
        if not rules:
            return {}

        profile_scope_map = {
            (profile.resource_type, profile.resource_id): profile.scope_key
            for profile in access_profile_registry.list_profiles()
        }

        code_scope_keys: dict[str, set[str]] = {}
        for rule in rules:
            scope_key = profile_scope_map.get((rule.resource_type, rule.resource_id), 'global')
            code_scope_keys.setdefault(rule.entitlement_code, set()).add(scope_key)

        resolved_scope_keys: dict[str, str] = {}
        for code, scope_keys in code_scope_keys.items():
            non_global_scope_keys = {scope_key for scope_key in scope_keys if scope_key != 'global'}
            if len(non_global_scope_keys) == 1:
                resolved_scope_keys[code] = next(iter(non_global_scope_keys))
                continue
            if not non_global_scope_keys and len(scope_keys) == 1:
                resolved_scope_keys[code] = next(iter(scope_keys))

        return resolved_scope_keys

    @staticmethod
    def _compute_quota_limits_from_items(
        pack_items: list[dict[str, Any]],
        quota_codes: list[str],
    ) -> dict[str, int]:
        """
        从聚合行计算配额上限

        :param pack_items: 权益包成员行
        :param quota_codes: 配额权益编码
        :return:
        """
        code_set = set(quota_codes)
        quota_limits: dict[str, int] = {}
        for item in pack_items:
            code = item.get('entitlement_code')
            if code not in code_set:
                continue

            value = item.get('value_int')
            value = value if value is not None else 0
            if value > quota_limits.get(str(code), 0):
                quota_limits[str(code)] = value
        return quota_limits

    @staticmethod
    async def _load_quota_balances(
        db: AsyncSession,
        *,
        user_id: int,
        now: datetime,
        pack_items: list[dict[str, Any]],
        quota_codes: list[str],
    ) -> dict[str, int]:
        """
        加载配额权益余额(直接聚合额度包)

        余额是当前所有有效额度包剩余量之和, 已天然包含周期补账额度与
        活动赠送的一次性额度, 因此不再需要按 cycle_type 逐级推导周期键。

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param now: 当前时间
        :param pack_items: 权益包成员行
        :param quota_codes: 配额权益编码
        :return:
        """
        if not quota_codes:
            return {}

        from backend.app.access.crud.crud_quota_grant import quota_grant_dao

        scope_keys = await MyAccessService._get_quota_scope_keys_from_rules(db, quota_codes)
        grouped: dict[str, list[str]] = {}
        for code in quota_codes:
            grouped.setdefault(scope_keys.get(code, 'global'), []).append(code)

        balances: dict[str, int] = {}
        for scope_key, codes in grouped.items():
            balances.update(
                await quota_grant_dao.get_balances(
                    db,
                    user_id=user_id,
                    entitlement_codes=codes,
                    scope_key=scope_key,
                    ts=now,
                )
            )

        missing_codes = sorted(set(quota_codes) - set(balances))
        if not missing_codes:
            return balances

        # 尚未生成过额度包(订阅后从未使用)时, 按权益包配置展示名义额度
        fallback_limits = MyAccessService._compute_quota_limits_from_items(
            pack_items,
            missing_codes,
        )
        for code in missing_codes:
            balances[code] = fallback_limits.get(code, 0)

        return balances

    @staticmethod
    def _build_subscription_items_from_rows(rows: Sequence[Row]) -> list[GetMySubscription]:
        """
        从聚合行构建我的订阅项

        :param rows: 聚合查询行
        :return:
        """
        grouped: dict[int, dict[str, Any]] = {}
        for row in rows:
            item = grouped.setdefault(
                row.subscription_id,
                {
                    'id': row.subscription_id,
                    'template_id': row.template_id,
                    'template_code': row.template_code,
                    'template_name': row.template_name,
                    'cover_image': row.cover_image,
                    'valid_period': row.valid_period,
                    'valid_from': row.valid_period.lower,
                    'valid_to': row.valid_period.upper,
                    'status': row.status,
                    'created_time': row.created_time,
                    'packs': [],
                    'domain_codes': [],
                },
            )
            if row.pack_id is not None:
                item['packs'].append({
                    'id': row.pack_id,
                    'code': row.pack_code,
                })
            if row.domain_code and row.domain_code not in item['domain_codes']:
                item['domain_codes'].append(row.domain_code)

        result: list[GetMySubscription] = []
        for item in grouped.values():
            packs = item['packs']
            result.append(
                GetMySubscription(
                    id=item['id'],
                    template_code=item['template_code'],
                    template_name=item['template_name'],
                    pack_code=packs[0]['code'] if packs else None,
                    pack_codes=[pack['code'] for pack in packs],
                    domain_codes=item['domain_codes'],
                    cover_image=item['cover_image'],
                    valid_period=TimePeriodOutput.from_range(item['valid_period']),
                    valid_from=item['valid_from'],
                    valid_to=item['valid_to'],
                    status=item['status'],
                    created_time=item['created_time'],
                )
            )
        return result

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
