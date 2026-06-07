#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import LedgerOperation
from backend.app.access.model.ledger import QuotaLedger


class CRUDQuotaLedger(CRUDPlus[QuotaLedger]):
    """配额账本 CRUD"""

    async def get_current_balance(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        scope_key: str,
        cycle_key: str,
    ) -> int:
        """
        获取当前余额(取最新一条 balance_after)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param scope_key: 业务范围键
        :param cycle_key: 周期键
        :return:
        """
        stmt = (
            select(self.model.balance_after)
            .where(
                self.model.user_id == user_id,
                self.model.entitlement_code == entitlement_code,
                self.model.scope_key == scope_key,
                self.model.cycle_key == cycle_key,
            )
            .order_by(self.model.occurred_at.desc(), self.model.id.desc())
            .limit(1)
        )
        balance = (await db.execute(stmt)).scalar()
        return int(balance or 0)

    async def get_latest_entry(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        scope_key: str,
        cycle_key: str,
    ) -> QuotaLedger | None:
        """
        获取当前周期最新流水

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param scope_key: 业务范围键
        :param cycle_key: 周期键
        :return:
        """
        stmt = (
            select(self.model)
            .where(
                self.model.user_id == user_id,
                self.model.entitlement_code == entitlement_code,
                self.model.scope_key == scope_key,
                self.model.cycle_key == cycle_key,
            )
            .order_by(self.model.occurred_at.desc(), self.model.id.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_latest_entries(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_cycle_keys: dict[str, str],
        scope_key: str,
    ) -> dict[str, int]:
        """
        批量获取当前周期最新余额

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_cycle_keys: 权益编码与周期键映射
        :param scope_key: 业务范围键
        :return:
        """
        if not entitlement_cycle_keys:
            return {}

        pairs = list(entitlement_cycle_keys.items())
        stmt = (
            select(
                self.model.entitlement_code.label('entitlement_code'),
                self.model.balance_after.label('balance_after'),
            )
            .where(
                self.model.user_id == user_id,
                self.model.scope_key == scope_key,
                tuple_(self.model.entitlement_code, self.model.cycle_key).in_(pairs),
            )
            .distinct(self.model.entitlement_code)
            .order_by(
                self.model.entitlement_code.asc(),
                self.model.occurred_at.desc(),
                self.model.id.desc(),
            )
        )
        rows = (await db.execute(stmt)).all()
        return {str(row.entitlement_code): int(row.balance_after or 0) for row in rows}

    async def get_by_idempotency_key(
        self,
        db: AsyncSession,
        idempotency_key: str,
    ) -> QuotaLedger | None:
        """
        通过幂等键查询流水

        :param db: 数据库会话
        :param idempotency_key: 幂等键
        :return:
        """
        stmt = select(self.model).where(self.model.idempotency_key == idempotency_key)
        return (await db.execute(stmt)).scalars().first()

    async def list_for_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str | None = None,
        cycle_key: str | None = None,
        limit: int = 100,
    ) -> Sequence[QuotaLedger]:
        """
        列出用户账本流水

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param cycle_key: 周期键
        :param limit: 数量上限
        :return:
        """
        stmt = select(self.model).where(self.model.user_id == user_id)
        if entitlement_code:
            stmt = stmt.where(self.model.entitlement_code == entitlement_code)
        if cycle_key:
            stmt = stmt.where(self.model.cycle_key == cycle_key)
        stmt = stmt.order_by(self.model.occurred_at.desc(), self.model.id.desc()).limit(limit)
        return (await db.execute(stmt)).scalars().all()

    async def get_select(
        self,
        *,
        user_id: int | None = None,
        entitlement_code: str | None = None,
        operation: LedgerOperation | None = None,
        cycle_key: str | None = None,
    ) -> Select:
        """
        分页查询语句

        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param operation: 操作类型
        :param cycle_key: 周期键
        :return:
        """
        filters: dict[str, object] = {}
        if user_id is not None:
            filters['user_id__eq'] = user_id
        if entitlement_code is not None:
            filters['entitlement_code__eq'] = entitlement_code
        if operation is not None:
            filters['operation__eq'] = operation
        if cycle_key is not None:
            filters['cycle_key__eq'] = cycle_key
        return await self.select_order('occurred_at', 'desc', **filters)


quota_ledger_dao: CRUDQuotaLedger = CRUDQuotaLedger(QuotaLedger)
