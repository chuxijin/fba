#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import LedgerOperation
from backend.app.access.model.ledger import QuotaLedger


class CRUDQuotaLedger(CRUDPlus[QuotaLedger]):
    """配额账本 CRUD(审计流水)

    余额不再从账本推导, 请使用 quota_grant_dao 聚合额度包。
    """

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
