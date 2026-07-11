#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CycleType, EntitlementCategory, LedgerOperation
from backend.app.access.crud.crud_entitlement import entitlement_dao
from backend.app.access.crud.crud_ledger import quota_ledger_dao
from backend.app.access.crud.crud_pack import pack_item_dao
from backend.app.access.crud.crud_subscription import subscription_dao
from backend.app.access.crud.crud_template import template_pack_dao
from backend.app.access.engine.cycle import build_cycle_key
from backend.app.access.model.ledger import QuotaLedger
from backend.common.exception import errors
from backend.utils.timezone import timezone


class LedgerService:
    """配额账本服务(事件溯源 + 幂等)"""

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
        获取当前余额

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param scope_key: 业务范围键
        :param cycle_type: 周期类型
        :param cycle_key: 周期键, 空则按 ts 算
        :param ts: 时间点, 空则取当前
        :return:
        """
        key = cycle_key or build_cycle_key(cycle_type, ts)
        return await cls._ensure_cycle_quota(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            scope_key=scope_key,
            cycle_type=cycle_type,
            cycle_key=key,
            ts=ts,
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
    ) -> QuotaLedger:
        """
        入账(增加余额)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param amount: 入账数量
        :param cycle_type: 周期类型
        :param cycle_key: 周期键
        :param scope_key: 业务范围键
        :param source: 来源标识
        :param source_ref: 来源引用
        :param idempotency_key: 幂等键
        :param reason: 原因
        :return:
        """
        if amount <= 0:
            raise errors.RequestError(msg='入账数量必须大于 0')
        return await cls._append(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            operation=LedgerOperation.CREDIT,
            amount=amount,
            cycle_type=cycle_type,
            cycle_key=cycle_key,
            scope_key=scope_key,
            source=source,
            source_ref=source_ref,
            idempotency_key=idempotency_key,
            reason=reason,
        )

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
    ) -> QuotaLedger | None:
        """
        尝试扣减(余额不足返回 None, 幂等)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param amount: 扣减数量
        :param cycle_type: 周期类型
        :param cycle_key: 周期键
        :param scope_key: 业务范围键
        :param source: 来源标识
        :param source_ref: 来源引用
        :param idempotency_key: 幂等键
        :param reason: 原因
        :return:
        """
        if amount <= 0:
            raise errors.RequestError(msg='扣减数量必须大于 0')

        if idempotency_key:
            existing = await quota_ledger_dao.get_by_idempotency_key(db, idempotency_key)
            if existing is not None:
                return existing

        key = cycle_key or build_cycle_key(cycle_type)
        balance = await cls._ensure_cycle_quota(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            scope_key=scope_key,
            cycle_type=cycle_type,
            cycle_key=key,
        )
        if balance < amount:
            return None

        return await cls._append(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            operation=LedgerOperation.DEBIT,
            amount=amount,
            cycle_type=cycle_type,
            cycle_key=key,
            scope_key=scope_key,
            source=source,
            source_ref=source_ref,
            idempotency_key=idempotency_key,
            reason=reason,
            current_balance=balance,
        )

    @classmethod
    async def _ensure_cycle_quota(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        scope_key: str,
        cycle_type: str,
        cycle_key: str,
        ts: datetime | None = None,
    ) -> int:
        """
        确保当前周期订阅配额已初始化

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param scope_key: 业务范围键
        :param cycle_type: 周期类型
        :param cycle_key: 周期键
        :param ts: 时间点
        :return:
        """
        latest = await quota_ledger_dao.get_latest_entry(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            scope_key=scope_key,
            cycle_key=cycle_key,
        )
        if latest is not None:
            return latest.balance_after

        amount = await cls._resolve_subscription_quota_limit(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            cycle_type=cycle_type,
            ts=ts,
        )
        if amount <= 0:
            return 0

        idempotency_key = cls._build_refill_idempotency_key(
            user_id=user_id,
            entitlement_code=entitlement_code,
            scope_key=scope_key,
            cycle_type=cycle_type,
            cycle_key=cycle_key,
        )
        existing = await quota_ledger_dao.get_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return existing.balance_after

        cycle_value = cls._normalise_cycle_type(cycle_type)
        entry = await cls.credit(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            amount=amount,
            cycle_type=cycle_type,
            cycle_key=cycle_key,
            scope_key=scope_key,
            source='subscription_quota',
            source_ref=f'{cycle_value}:{cycle_key}',
            idempotency_key=idempotency_key,
            reason='subscription quota refill',
        )
        return entry.balance_after

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
        cycle_value = cls._normalise_cycle_type(cycle_type)
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
    def _normalise_cycle_type(cycle_type: str) -> str:
        """
        标准化周期类型

        :param cycle_type: 周期类型
        :return:
        """
        return str(getattr(cycle_type, 'value', cycle_type))

    @classmethod
    def _get_pack_item_cycle_type(cls, value_meta: dict | None) -> str:
        """
        获取权益包成员周期类型

        :param value_meta: 扩展参数
        :return:
        """
        if not value_meta:
            return cls._normalise_cycle_type(CycleType.MONTHLY)
        cycle_type = value_meta.get('cycle_type') or CycleType.MONTHLY
        return cls._normalise_cycle_type(cycle_type)

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
        cycle_value = cls._normalise_cycle_type(cycle_type)
        raw_key = f'{user_id}:{entitlement_code}:{scope_key}:{cycle_value}:{cycle_key}'
        digest = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        return f'quota_refill:{digest}'

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
    ) -> QuotaLedger:
        """
        回滚配额(幂等, source_ref 必填)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param amount: 回滚数量
        :param cycle_type: 周期类型
        :param cycle_key: 周期键
        :param scope_key: 业务范围键
        :param source: 来源标识
        :param source_ref: 关联的原扣减引用
        :param idempotency_key: 幂等键
        :param reason: 原因
        :return:
        """
        if amount <= 0:
            raise errors.RequestError(msg='回滚数量必须大于 0')

        existing = await quota_ledger_dao.get_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return existing

        return await cls._append(
            db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            operation=LedgerOperation.REFUND,
            amount=amount,
            cycle_type=cycle_type,
            cycle_key=cycle_key,
            scope_key=scope_key,
            source=source,
            source_ref=source_ref,
            idempotency_key=idempotency_key,
            reason=reason,
        )

    @classmethod
    async def _append(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        operation: LedgerOperation,
        amount: int,
        cycle_type: str,
        cycle_key: str | None,
        scope_key: str,
        source: str,
        source_ref: str | None,
        idempotency_key: str | None,
        reason: str | None,
        current_balance: int | None = None,
    ) -> QuotaLedger:
        """
        追加一条流水(内部统一入口)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param operation: 操作类型
        :param amount: 数量
        :param cycle_type: 周期类型
        :param cycle_key: 周期键
        :param scope_key: 业务范围键
        :param source: 来源
        :param source_ref: 来源引用
        :param idempotency_key: 幂等键
        :param reason: 原因
        :param current_balance: 已知的当前余额(避免重复查询)
        :return:
        """
        key = cycle_key or build_cycle_key(cycle_type)
        if current_balance is None:
            current_balance = await quota_ledger_dao.get_current_balance(
                db,
                user_id=user_id,
                entitlement_code=entitlement_code,
                scope_key=scope_key,
                cycle_key=key,
            )

        new_balance = cls._compute_balance(current_balance, operation, amount)
        entry = QuotaLedger(
            user_id=user_id,
            entitlement_code=entitlement_code,
            cycle_type=cycle_type,
            cycle_key=key,
            operation=operation,
            amount=amount,
            balance_after=new_balance,
            source=source,
            scope_key=scope_key,
            source_ref=source_ref,
            idempotency_key=idempotency_key,
            reason=reason,
        )
        db.add(entry)
        await db.flush()
        from backend.app.access.service.my_service import my_summary_cache

        await my_summary_cache.invalidate(user_id)
        return entry

    @staticmethod
    def _compute_balance(current: int, operation: LedgerOperation, amount: int) -> int:
        """
        根据操作类型计算新余额

        :param current: 当前余额
        :param operation: 操作类型
        :param amount: 数量
        :return:
        """
        if operation in (LedgerOperation.CREDIT, LedgerOperation.REFUND):
            return current + amount
        if operation == LedgerOperation.DEBIT:
            return max(current - amount, 0)
        if operation == LedgerOperation.RESET:
            return 0
        if operation == LedgerOperation.ADJUST:
            return max(amount, 0)
        return current


ledger_service: LedgerService = LedgerService()
