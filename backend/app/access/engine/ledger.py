#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import (
    CycleType,
    EntitlementCategory,
    LedgerOperation,
    QuotaGrantSource,
)
from backend.app.access.crud.crud_entitlement import entitlement_dao
from backend.app.access.crud.crud_ledger import quota_ledger_dao
from backend.app.access.crud.crud_pack import pack_item_dao
from backend.app.access.crud.crud_quota_grant import quota_grant_dao
from backend.app.access.crud.crud_subscription import subscription_dao
from backend.app.access.crud.crud_template import template_pack_dao
from backend.app.access.engine.cycle import build_cycle_end, build_cycle_key
from backend.app.access.model.ledger import QuotaLedger
from backend.app.access.model.quota_grant import QuotaGrant
from backend.common.exception import errors
from backend.utils.timezone import timezone

# 区分"未传 expires_at"(按周期推算)与"显式传 None"(永不过期)
_UNSET: Any = object()


class LedgerService:
    """配额服务(额度包为真相源, 账本为审计流水)

    余额 = 当前所有有效额度包 remaining_amount 之和, 不再按周期分桶,
    因此周期补账额度与活动赠送的一次性额度可以并存并统一计算。
    扣减按 expires_at 升序跨包消耗, 实现"优先扣即将失效的配额"。
    """

    @classmethod
    async def get_balance(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        scope_key: str = 'global',
        cycle_type: str = CycleType.MONTHLY,
        cycle_key: str | None = None,
        ts: datetime | None = None,
    ) -> int:
        """
        获取当前余额(会惰性补齐当前周期的订阅额度包)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param scope_key: 业务范围键
        :param cycle_type: 订阅补账的周期类型
        :param cycle_key: 周期键, 空则按 ts 算
        :param ts: 时间点, 空则取当前
        :return:
        """
        now = ts or timezone.now()
        await cls._ensure_cycle_grant(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            scope_key=scope_key,
            cycle_type=cycle_type,
            cycle_key=cycle_key,
            ts=now,
        )
        return await quota_grant_dao.get_balance(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            scope_key=scope_key,
            ts=now,
        )

    @classmethod
    async def credit(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        amount: int,
        cycle_type: str,
        cycle_key: str | None = None,
        scope_key: str = 'global',
        source: str,
        source_ref: str | None = None,
        idempotency_key: str | None = None,
        reason: str | None = None,
        expires_at: Any = _UNSET,
        priority: int = 0,
        ts: datetime | None = None,
    ) -> QuotaGrant:
        """
        发放一个额度包

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param amount: 发放数量
        :param cycle_type: 周期类型, 决定默认过期时间
        :param cycle_key: 周期键
        :param scope_key: 业务范围键
        :param source: 额度来源
        :param source_ref: 来源引用
        :param idempotency_key: 幂等键
        :param reason: 原因
        :param expires_at: 过期时间, 不传按周期推算, 显式传 None 表示永不过期
        :param priority: 同过期时间时的扣减优先级
        :param ts: 时间点
        :return:
        """
        if amount <= 0:
            raise errors.RequestError(msg='入账数量必须大于 0')

        now = ts or timezone.now()
        grant, created = await cls._create_grant(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            amount=amount,
            cycle_type=cycle_type,
            cycle_key=cycle_key,
            scope_key=scope_key,
            source=source,
            source_ref=source_ref,
            idempotency_key=idempotency_key,
            reason=reason,
            expires_at=expires_at,
            priority=priority,
            ts=now,
        )
        if not created:
            return grant

        balance_after = await quota_grant_dao.get_balance(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            scope_key=scope_key,
            ts=now,
        )
        await cls._append_ledger(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            operation=LedgerOperation.CREDIT,
            amount=amount,
            balance_after=balance_after,
            cycle_type=cycle_type,
            cycle_key=grant.cycle_key or build_cycle_key(cycle_type, now),
            scope_key=scope_key,
            source=source,
            source_ref=source_ref,
            idempotency_key=idempotency_key,
            reason=reason,
            grant_breakdown=[{'grant_id': grant.id, 'amount': amount}],
        )
        await cls._invalidate_summary(user_id)
        return grant

    @classmethod
    async def try_consume(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        amount: int = 1,
        cycle_type: str = CycleType.MONTHLY,
        cycle_key: str | None = None,
        scope_key: str = 'global',
        source: str,
        source_ref: str | None = None,
        idempotency_key: str | None = None,
        reason: str | None = None,
        ts: datetime | None = None,
    ) -> QuotaLedger | None:
        """
        尝试扣减(余额不足返回 None, 幂等)

        按 expires_at 升序跨额度包扣减, 优先消耗即将失效的额度。

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param amount: 扣减数量
        :param cycle_type: 订阅补账的周期类型
        :param cycle_key: 周期键
        :param scope_key: 业务范围键
        :param source: 来源标识
        :param source_ref: 来源引用
        :param idempotency_key: 幂等键
        :param reason: 原因
        :param ts: 时间点
        :return:
        """
        if amount <= 0:
            raise errors.RequestError(msg='扣减数量必须大于 0')

        if idempotency_key:
            existing = await quota_ledger_dao.get_by_idempotency_key(db, idempotency_key)
            if existing is not None:
                return existing

        now = ts or timezone.now()
        await cls._ensure_cycle_grant(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            scope_key=scope_key,
            cycle_type=cycle_type,
            cycle_key=cycle_key,
            ts=now,
        )

        grants = await quota_grant_dao.list_consumable(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            scope_key=scope_key,
            ts=now,
            for_update=True,
        )
        total = sum(grant.remaining_amount for grant in grants)
        if total < amount:
            return None

        breakdown: list[dict[str, int]] = []
        outstanding = amount
        for grant in grants:
            if outstanding <= 0:
                break
            taken = min(grant.remaining_amount, outstanding)
            grant.remaining_amount -= taken
            outstanding -= taken
            breakdown.append({'grant_id': grant.id, 'amount': taken})

        entry = await cls._append_ledger(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            operation=LedgerOperation.DEBIT,
            amount=amount,
            balance_after=total - amount,
            cycle_type=cycle_type,
            cycle_key=cycle_key or build_cycle_key(cycle_type, now),
            scope_key=scope_key,
            source=source,
            source_ref=source_ref,
            idempotency_key=idempotency_key,
            reason=reason,
            grant_breakdown=breakdown,
        )
        await cls._invalidate_summary(user_id)
        return entry

    @classmethod
    async def refund_consumption(
        cls,
        db: AsyncSession,
        *,
        ledger_id: int,
        source: str,
        source_ref: str,
        idempotency_key: str,
        reason: str | None = None,
        ts: datetime | None = None,
    ) -> QuotaLedger | None:
        """
        按原扣减流水精确回补额度包(幂等)

        回补到当初被扣的那些包, 保持各包的过期语义不变;
        若原流水没有额度包明细(迁移前的历史数据), 退化为发放一个等量补偿包。

        :param db: 数据库会话
        :param ledger_id: 原扣减流水 ID
        :param source: 来源标识
        :param source_ref: 来源引用
        :param idempotency_key: 幂等键
        :param reason: 原因
        :param ts: 时间点
        :return:
        """
        existing = await quota_ledger_dao.get_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return existing

        origin = await quota_ledger_dao.select_model(db, ledger_id)
        if origin is None or origin.operation != LedgerOperation.DEBIT:
            return None

        now = ts or timezone.now()
        breakdown = [dict(item) for item in (origin.grant_breakdown or [])]

        if breakdown:
            grant_ids = [int(item['grant_id']) for item in breakdown]
            grants = await quota_grant_dao.get_by_ids(db, grant_ids, for_update=True)
            grant_map = {grant.id: grant for grant in grants}
            for item in breakdown:
                grant = grant_map.get(int(item['grant_id']))
                if grant is None:
                    continue
                restored = grant.remaining_amount + int(item['amount'])
                # 回补不得超过该包发放总量, 防止重复回滚放大额度
                grant.remaining_amount = min(grant.granted_amount, restored)
        else:
            grant, _ = await cls._create_grant(
                db,
                user_id=origin.user_id,
                entitlement_code=origin.entitlement_code,
                amount=origin.amount,
                cycle_type=origin.cycle_type,
                cycle_key=origin.cycle_key,
                scope_key=origin.scope_key,
                source=QuotaGrantSource.COMPENSATION,
                source_ref=source_ref,
                idempotency_key=f'{idempotency_key}:grant',
                reason=reason,
                ts=now,
            )
            breakdown = [{'grant_id': grant.id, 'amount': origin.amount}]

        balance_after = await quota_grant_dao.get_balance(
            db,
            user_id=origin.user_id,
            entitlement_code=origin.entitlement_code,
            scope_key=origin.scope_key,
            ts=now,
        )
        entry = await cls._append_ledger(
            db,
            user_id=origin.user_id,
            entitlement_code=origin.entitlement_code,
            operation=LedgerOperation.REFUND,
            amount=origin.amount,
            balance_after=balance_after,
            cycle_type=origin.cycle_type,
            cycle_key=origin.cycle_key,
            scope_key=origin.scope_key,
            source=source,
            source_ref=source_ref,
            idempotency_key=idempotency_key,
            reason=reason,
            grant_breakdown=breakdown,
        )
        await cls._invalidate_summary(origin.user_id)
        return entry

    @classmethod
    async def refund(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        amount: int,
        cycle_type: str,
        cycle_key: str | None,
        scope_key: str = 'global',
        source: str,
        source_ref: str,
        idempotency_key: str,
        reason: str | None = None,
        expires_at: Any = _UNSET,
        ts: datetime | None = None,
    ) -> QuotaLedger:
        """
        通用回补(无原始流水时使用, 发放一个等量补偿包, 幂等)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param amount: 回补数量
        :param cycle_type: 周期类型
        :param cycle_key: 周期键
        :param scope_key: 业务范围键
        :param source: 来源标识
        :param source_ref: 来源引用
        :param idempotency_key: 幂等键
        :param reason: 原因
        :param expires_at: 过期时间, 不传按周期推算
        :param ts: 时间点
        :return:
        """
        if amount <= 0:
            raise errors.RequestError(msg='回滚数量必须大于 0')

        existing = await quota_ledger_dao.get_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return existing

        now = ts or timezone.now()
        grant, _ = await cls._create_grant(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            amount=amount,
            cycle_type=cycle_type,
            cycle_key=cycle_key,
            scope_key=scope_key,
            source=source,
            source_ref=source_ref,
            idempotency_key=f'{idempotency_key}:grant',
            reason=reason,
            expires_at=expires_at,
            ts=now,
        )
        balance_after = await quota_grant_dao.get_balance(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            scope_key=scope_key,
            ts=now,
        )
        entry = await cls._append_ledger(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            operation=LedgerOperation.REFUND,
            amount=amount,
            balance_after=balance_after,
            cycle_type=cycle_type,
            cycle_key=cycle_key or build_cycle_key(cycle_type, now),
            scope_key=scope_key,
            source=source,
            source_ref=source_ref,
            idempotency_key=idempotency_key,
            reason=reason,
            grant_breakdown=[{'grant_id': grant.id, 'amount': amount}],
        )
        await cls._invalidate_summary(user_id)
        return entry

    @classmethod
    async def _create_grant(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        amount: int,
        cycle_type: str,
        cycle_key: str | None,
        scope_key: str,
        source: str,
        source_ref: str | None,
        idempotency_key: str | None,
        reason: str | None,
        expires_at: Any = _UNSET,
        priority: int = 0,
        ts: datetime | None = None,
    ) -> tuple[QuotaGrant, bool]:
        """
        创建额度包(幂等)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param amount: 发放数量
        :param cycle_type: 周期类型
        :param cycle_key: 周期键
        :param scope_key: 业务范围键
        :param source: 额度来源
        :param source_ref: 来源引用
        :param idempotency_key: 幂等键
        :param reason: 原因
        :param expires_at: 过期时间, 不传按周期推算
        :param priority: 扣减优先级
        :param ts: 时间点
        :return: (额度包, 是否本次新建)
        """
        if idempotency_key:
            existing = await quota_grant_dao.get_by_idempotency_key(db, idempotency_key)
            if existing is not None:
                return existing, False

        now = ts or timezone.now()
        key = cycle_key or build_cycle_key(cycle_type, now)
        resolved_expires_at = build_cycle_end(cycle_type, now) if expires_at is _UNSET else expires_at

        grant = QuotaGrant(
            user_id=user_id,
            entitlement_code=entitlement_code,
            granted_amount=amount,
            remaining_amount=amount,
            source=cls._enum_value(source),
            scope_key=scope_key,
            effective_at=now,
            expires_at=resolved_expires_at,
            priority=priority,
            cycle_type=cls._enum_value(cycle_type),
            cycle_key=key,
            source_ref=source_ref,
            idempotency_key=idempotency_key,
            reason=reason,
        )
        db.add(grant)
        await db.flush()
        return grant, True

    @classmethod
    async def _append_ledger(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        operation: LedgerOperation,
        amount: int,
        balance_after: int,
        cycle_type: str,
        cycle_key: str,
        scope_key: str,
        source: str,
        source_ref: str | None,
        idempotency_key: str | None,
        reason: str | None,
        grant_breakdown: list[dict[str, int]],
    ) -> QuotaLedger:
        """
        追加一条审计流水

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param operation: 操作类型
        :param amount: 数量
        :param balance_after: 操作后全量有效余额
        :param cycle_type: 周期类型
        :param cycle_key: 周期键
        :param scope_key: 业务范围键
        :param source: 来源
        :param source_ref: 来源引用
        :param idempotency_key: 幂等键
        :param reason: 原因
        :param grant_breakdown: 本次命中的额度包明细
        :return:
        """
        entry = QuotaLedger(
            user_id=user_id,
            entitlement_code=entitlement_code,
            cycle_type=cls._enum_value(cycle_type),
            cycle_key=cycle_key,
            operation=operation,
            amount=amount,
            balance_after=balance_after,
            source=cls._enum_value(source),
            scope_key=scope_key,
            grant_breakdown=grant_breakdown,
            source_ref=source_ref,
            idempotency_key=idempotency_key,
            reason=reason,
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def _invalidate_summary(user_id: int) -> None:
        """
        失效我的权益汇总缓存

        :param user_id: 用户 ID
        :return:
        """
        from backend.app.access.service.my_service import my_summary_cache

        await my_summary_cache.invalidate(user_id)

    @classmethod
    async def _ensure_cycle_grant(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        scope_key: str,
        cycle_type: str,
        cycle_key: str | None,
        ts: datetime,
    ) -> None:
        """
        确保订阅授予的当前周期额度包已生成(幂等)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param scope_key: 业务范围键
        :param cycle_type: 周期类型
        :param cycle_key: 周期键
        :param ts: 时间点
        :return:
        """
        key = cycle_key or build_cycle_key(cycle_type, ts)
        idempotency_key = cls._build_refill_idempotency_key(
            user_id=user_id,
            entitlement_code=entitlement_code,
            scope_key=scope_key,
            cycle_type=cycle_type,
            cycle_key=key,
        )
        existing = await quota_grant_dao.get_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return

        amount = await cls._resolve_subscription_quota_limit(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            cycle_type=cycle_type,
            ts=ts,
        )
        if amount <= 0:
            return

        cycle_value = cls._enum_value(cycle_type)
        await cls.credit(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            amount=amount,
            cycle_type=cycle_type,
            cycle_key=key,
            scope_key=scope_key,
            source=QuotaGrantSource.SUBSCRIPTION,
            source_ref=f'{cycle_value}:{key}',
            idempotency_key=idempotency_key,
            reason='subscription quota refill',
            ts=ts,
        )

    @classmethod
    async def _resolve_subscription_quota_limit(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        cycle_type: str,
        ts: datetime | None,
    ) -> int:
        """
        获取订阅授予的当前周期配额上限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param cycle_type: 周期类型
        :param ts: 时间点
        :return:
        """
        entitlement = await entitlement_dao.get_by_code(db, entitlement_code)
        if not entitlement or entitlement.category != EntitlementCategory.QUOTA:
            return 0

        subscriptions = await subscription_dao.list_active_for_user(db, user_id, ts or timezone.now())
        if not subscriptions:
            return 0

        template_ids = [subscription.template_id for subscription in subscriptions]
        template_packs = await template_pack_dao.get_by_templates(db, template_ids)
        pack_ids = list({relation.pack_id for relation in template_packs})
        pack_items = await pack_item_dao.get_by_packs(db, pack_ids)

        entitlement_ids = list({item.entitlement_id for item in pack_items})
        entitlements = await entitlement_dao.get_by_ids(db, entitlement_ids)
        entitlement_map = {item.id: item for item in entitlements}

        limit = 0
        cycle_value = cls._enum_value(cycle_type)
        for item in pack_items:
            item_entitlement = entitlement_map.get(item.entitlement_id)
            if not item_entitlement or item_entitlement.code != entitlement_code:
                continue

            item_cycle_type = cls._get_pack_item_cycle_type(item.value_meta)
            if item_cycle_type != cycle_value:
                continue

            value = item.value_int if item.value_int is not None else 1
            if value > limit:
                limit = value
        return limit

    @staticmethod
    def _enum_value(value: object) -> str:
        """
        取枚举的字符串值(兼容入参已经是 str 的情况)

        :param value: 枚举或字符串
        :return:
        """
        return str(getattr(value, 'value', value))

    @classmethod
    def _get_pack_item_cycle_type(cls, value_meta: dict | None) -> str:
        """
        获取权益包成员周期类型

        :param value_meta: 扩展参数
        :return:
        """
        if not value_meta:
            return cls._enum_value(CycleType.MONTHLY)
        cycle_type = value_meta.get('cycle_type') or CycleType.MONTHLY
        return cls._enum_value(cycle_type)

    @classmethod
    def _build_refill_idempotency_key(
        cls,
        *,
        user_id: int,
        entitlement_code: str,
        scope_key: str,
        cycle_type: str,
        cycle_key: str,
    ) -> str:
        """
        构建周期补额幂等键

        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param scope_key: 范围键
        :param cycle_type: 周期类型
        :param cycle_key: 周期键
        :return:
        """
        cycle_value = cls._enum_value(cycle_type)
        raw_key = f'{user_id}:{entitlement_code}:{scope_key}:{cycle_value}:{cycle_key}'
        digest = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        return f'quota_refill:{digest}'


ledger_service: LedgerService = LedgerService()
