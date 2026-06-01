#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import Row

from backend.app.access.constants import (
    CycleType,
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
from backend.app.access.engine.cycle import build_cycle_key
from backend.app.access.model.entitlement import Entitlement
from backend.app.access.model.pack import EntitlementPack, PackItem
from backend.app.access.model.subscription import Subscription
from backend.app.access.model.template import SubscriptionTemplate
from backend.app.access.schema.base import TimePeriodOutput
from backend.app.access.schema.entitlement import GetMyEntitlement
from backend.app.access.schema.my import GetMyAccessSummary
from backend.app.access.schema.subscription import GetMySubscription, GetMySubscriptionLedger
from backend.app.access.service.subscription_service import subscription_service
from backend.database.redis import redis_client
from backend.utils.timezone import timezone


_MY_ACCESS_SUMMARY_CACHE_TTL = 30

_GRADE_WEIGHTS = {
    'basic': 0,
    'standard': 1,
    'premium': 2,
    'elite': 3,
}


class MyAccessService:
    """我的权益聚合服务"""

    @staticmethod
    def _summary_cache_key(user_id: int) -> str:
        """
        获取我的权益汇总缓存键

        :param user_id: 用户 ID
        :return:
        """
        return f'access:my:summary:{user_id}'

    @staticmethod
    async def invalidate_summary_cache(user_id: int) -> None:
        """
        删除我的权益汇总缓存

        :param user_id: 用户 ID
        :return:
        """
        await redis_client.delete(MyAccessService._summary_cache_key(user_id))

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

        # 聚合 QUOTA 类型权益的当前余额: 优先取 ledger 现存余额, 否则按 pack_item 配置回退
        quota_codes = [
            code
            for code, entitlement in entitlement_map.items()
            if entitlement['category'] == EntitlementCategory.QUOTA
        ]
        balances: dict[str, int] = {}
        if quota_codes:
            cycle_types = MyAccessService._get_quota_cycle_types_from_items(pack_items, quota_codes)
            # 从 resource_rule metadata 补查未命中的配额周期类型
            missing_cycle_codes = [code for code in quota_codes if code not in cycle_types]
            if missing_cycle_codes:
                rule_cycle_types = await MyAccessService._get_quota_cycle_types_from_rules(
                    db, missing_cycle_codes,
                )
                cycle_types.update(rule_cycle_types)
            entitlement_cycle_keys = {
                code: build_cycle_key(cycle_types.get(code, CycleType.MONTHLY), now)
                for code in quota_codes
            }
            from backend.app.access.crud.crud_ledger import quota_ledger_dao

            balances = await quota_ledger_dao.get_latest_entries(
                db,
                user_id=user_id,
                entitlement_cycle_keys=entitlement_cycle_keys,
                scope_key='global',
            )

            missing_codes = sorted(set(quota_codes) - set(balances))
            if missing_codes:
                fallback_limits = MyAccessService._compute_quota_limits_from_items(
                    pack_items,
                    missing_codes,
                )
                for code in missing_codes:
                    balances[code] = fallback_limits.get(code, 0)

        entitlement_map = MyAccessService._filter_covered_trials(entitlement_map)
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
    ) -> list[GetMyEntitlement]:
        """
        从订阅权益聚合行构建权益列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param now: 当前时间
        :param subscription_rows: 订阅权益聚合行
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

        quota_codes = [
            code
            for code, entitlement in entitlement_map.items()
            if entitlement['category'] == EntitlementCategory.QUOTA
        ]
        balances: dict[str, int] = {}
        if quota_codes:
            cycle_types = MyAccessService._get_quota_cycle_types_from_items(pack_items, quota_codes)
            # 从 resource_rule metadata 补查未命中的配额周期类型
            missing_cycle_codes = [code for code in quota_codes if code not in cycle_types]
            if missing_cycle_codes:
                rule_cycle_types = await MyAccessService._get_quota_cycle_types_from_rules(
                    db, missing_cycle_codes,
                )
                cycle_types.update(rule_cycle_types)
            entitlement_cycle_keys = {
                code: build_cycle_key(cycle_types.get(code, CycleType.MONTHLY), now)
                for code in quota_codes
            }
            from backend.app.access.crud.crud_ledger import quota_ledger_dao

            balances = await quota_ledger_dao.get_latest_entries(
                db,
                user_id=user_id,
                entitlement_cycle_keys=entitlement_cycle_keys,
                scope_key='global',
            )

            missing_codes = sorted(set(quota_codes) - set(balances))
            if missing_codes:
                fallback_limits = MyAccessService._compute_quota_limits_from_items(
                    pack_items,
                    missing_codes,
                )
                for code in missing_codes:
                    balances[code] = fallback_limits.get(code, 0)

        entitlement_map = MyAccessService._filter_covered_trials(entitlement_map)
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
        cache_key = MyAccessService._summary_cache_key(user_id)
        if not force_refresh:
            cache_value = await redis_client.get(cache_key)
            if cache_value:
                return GetMyAccessSummary.model_validate_json(cache_value)

        now = timezone.now()

        graph_rows = await subscription_dao.list_my_access_graph_rows(db, user_id=user_id, ts=now)

        subscriptions = MyAccessService._build_subscription_items_from_rows(graph_rows)

        entitlements = await MyAccessService._build_entitlements_from_rows(
            db,
            user_id=user_id,
            now=now,
            subscription_rows=graph_rows,
        )
        result = GetMyAccessSummary(
            subscriptions=subscriptions,
            entitlements=entitlements,
        )
        await redis_client.setex(
            cache_key,
            _MY_ACCESS_SUMMARY_CACHE_TTL,
            result.model_dump_json(),
        )
        return result

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
    def _get_quota_cycle_types(
        subscription_context: dict[str, object],
        quota_codes: list[str],
    ) -> dict[str, str]:
        """
        获取订阅配额权益的周期类型

        :param subscription_context: 订阅权益上下文
        :param quota_codes: 配额权益编码
        :return:
        """
        code_set = set(quota_codes)
        pack_items = subscription_context.get('pack_items')
        entitlement_map = subscription_context.get('entitlement_map')
        if not isinstance(pack_items, list) or not isinstance(entitlement_map, dict):
            return {}

        cycle_types: dict[str, str] = {}
        quota_values: dict[str, int] = {}
        for item in pack_items:
            if not isinstance(item, PackItem):
                continue

            entitlement = entitlement_map.get(item.entitlement_id)
            if not isinstance(entitlement, Entitlement) or entitlement.code not in code_set:
                continue

            value = item.value_int if item.value_int is not None else 1
            current_value = quota_values.get(entitlement.code, 0)
            if value < current_value:
                continue

            value_meta = item.value_meta or {}
            cycle_type = value_meta.get('cycle_type') or CycleType.MONTHLY
            cycle_types[entitlement.code] = str(getattr(cycle_type, 'value', cycle_type))
            quota_values[entitlement.code] = value
        return cycle_types

    @staticmethod
    def _compute_quota_limits_from_context(
        subscription_context: dict[str, object],
        quota_codes: list[str],
    ) -> dict[str, int]:
        """
        从订阅上下文直接计算配额上限, 避免落 ledger 时的多次查询

        :param subscription_context: 订阅权益上下文
        :param quota_codes: 配额权益编码
        :return:
        """
        code_set = set(quota_codes)
        pack_items = subscription_context.get('pack_items')
        entitlement_map = subscription_context.get('entitlement_map')
        if not isinstance(pack_items, list) or not isinstance(entitlement_map, dict):
            return {}

        quota_limits: dict[str, int] = {}
        for item in pack_items:
            if not isinstance(item, PackItem):
                continue

            entitlement = entitlement_map.get(item.entitlement_id)
            if not isinstance(entitlement, Entitlement) or entitlement.code not in code_set:
                continue

            value = item.value_int if item.value_int is not None else 0
            if value > quota_limits.get(entitlement.code, 0):
                quota_limits[entitlement.code] = value
        return quota_limits

    @staticmethod
    def _get_quota_cycle_types_from_items(
        pack_items: list[dict[str, Any]],
        quota_codes: list[str],
    ) -> dict[str, str]:
        """
        从聚合行获取配额周期类型

        :param pack_items: 权益包成员行
        :param quota_codes: 配额权益编码
        :return:
        """
        code_set = set(quota_codes)
        cycle_types: dict[str, str] = {}
        quota_values: dict[str, int] = {}
        for item in pack_items:
            code = item.get('entitlement_code')
            if code not in code_set:
                continue

            value = item.get('value_int')
            value = value if value is not None else 1
            current_value = quota_values.get(str(code), 0)
            if value < current_value:
                continue

            value_meta = item.get('value_meta') or {}
            cycle_type = value_meta.get('cycle_type') or CycleType.MONTHLY
            cycle_types[str(code)] = str(getattr(cycle_type, 'value', cycle_type))
            quota_values[str(code)] = value
        return cycle_types

    @staticmethod
    def _filter_covered_trials(entitlement_map: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """
        过滤被完整权限覆盖的试看配额

        若用户拥有 access 类型的 *.view 权益, 则隐藏同前缀的 *.trial 配额

        :param entitlement_map: 权益映射
        :return:
        """
        access_codes = {
            code for code, ent in entitlement_map.items()
            if ent['category'] == EntitlementCategory.ACCESS
        }
        return {
            code: ent for code, ent in entitlement_map.items()
            if not (code.endswith('.trial') and code.replace('.trial', '.view') in access_codes)
        }

    @staticmethod
    async def _get_quota_cycle_types_from_rules(
        db: AsyncSession,
        quota_codes: list[str],
    ) -> dict[str, str]:
        """
        从 resource_rule metadata 获取配额周期类型

        :param db: 数据库会话
        :param quota_codes: 配额权益编码
        :return:
        """
        from sqlalchemy import select as sa_select

        from backend.app.access.model.rule import ResourceRule

        stmt = sa_select(ResourceRule).where(
            ResourceRule.entitlement_code.in_(quota_codes),
            ResourceRule.status == 'active',
        )
        rules = (await db.execute(stmt)).scalars().all()
        cycle_types: dict[str, str] = {}
        for rule in rules:
            cycle_type = (rule.metadata_ or {}).get('cycle_type', CycleType.MONTHLY)
            cycle_types[rule.entitlement_code] = str(getattr(cycle_type, 'value', cycle_type))
        return cycle_types

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
                    'grade': MyAccessService._source_value(row.pack_grade),
                })
            if row.domain_code and row.domain_code not in item['domain_codes']:
                item['domain_codes'].append(row.domain_code)

        result: list[GetMySubscription] = []
        for item in grouped.values():
            primary_pack = MyAccessService._primary_pack_dict(item['packs'])
            result.append(
                GetMySubscription(
                    id=item['id'],
                    template_code=item['template_code'],
                    template_name=item['template_name'],
                    pack_code=primary_pack['code'] if primary_pack else None,
                    grade=primary_pack['grade'] if primary_pack else 'basic',
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
    def _primary_pack_dict(packs: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
        """
        获取主权益包字典

        :param packs: 权益包字典列表
        :return:
        """
        if not packs:
            return None
        return sorted(
            packs,
            key=lambda pack: _GRADE_WEIGHTS.get(str(pack.get('grade')), 0),
            reverse=True,
        )[0]

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
    def _build_entitlement_item(entitlement: Entitlement, balance: int | None = None) -> GetMyEntitlement:
        """
        构建我的权益项

        :param entitlement: 权益
        :param balance: 余额
        :return:
        """
        return GetMyEntitlement(
            code=entitlement.code,
            name=entitlement.name,
            category=entitlement.category,
            description=entitlement.description,
            balance=balance,
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
