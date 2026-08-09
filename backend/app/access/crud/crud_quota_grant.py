#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import CommonStatus
from backend.app.access.model.quota_grant import QuotaGrant


class CRUDQuotaGrant(CRUDPlus[QuotaGrant]):
    """配额额度包 CRUD"""

    def _valid_clauses(self, ts: datetime) -> list[ColumnElement[bool]]:
        """
        构造"当前有效额度包"的过滤条件

        :param ts: 时间点
        :return:
        """
        return [
            self.model.status == CommonStatus.ACTIVE,
            self.model.effective_at <= ts,
            (self.model.expires_at.is_(None)) | (self.model.expires_at > ts),
        ]

    async def get_balance(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        scope_key: str,
        ts: datetime,
    ) -> int:
        """
        获取当前有效余额(所有有效额度包剩余量之和)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param scope_key: 业务范围键
        :param ts: 时间点
        :return:
        """
        stmt = select(func.coalesce(func.sum(self.model.remaining_amount), 0)).where(
            self.model.user_id == user_id,
            self.model.entitlement_code == entitlement_code,
            self.model.scope_key == scope_key,
            *self._valid_clauses(ts),
        )
        return int((await db.execute(stmt)).scalar() or 0)

    async def get_balances(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_codes: Sequence[str],
        scope_key: str,
        ts: datetime,
    ) -> dict[str, int]:
        """
        批量获取多个权益编码的当前有效余额

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_codes: 权益编码列表
        :param scope_key: 业务范围键
        :param ts: 时间点
        :return: 仅包含存在额度包的编码
        """
        if not entitlement_codes:
            return {}

        stmt = (
            select(
                self.model.entitlement_code.label('entitlement_code'),
                func.coalesce(func.sum(self.model.remaining_amount), 0).label('balance'),
            )
            .where(
                self.model.user_id == user_id,
                self.model.entitlement_code.in_(list(entitlement_codes)),
                self.model.scope_key == scope_key,
                *self._valid_clauses(ts),
            )
            .group_by(self.model.entitlement_code)
        )
        rows = (await db.execute(stmt)).all()
        return {str(row.entitlement_code): int(row.balance or 0) for row in rows}

    async def list_consumable(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        scope_key: str,
        ts: datetime,
        for_update: bool = False,
    ) -> Sequence[QuotaGrant]:
        """
        按扣减顺序列出可消耗的额度包

        排序即业务规则: 先扣即将失效的(expires_at 升序, 永不过期的排最后),
        同过期时间时按 priority 降序, 最后按 id 升序保证确定性。

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param scope_key: 业务范围键
        :param ts: 时间点
        :param for_update: 是否加行锁
        :return:
        """
        stmt = (
            select(self.model)
            .where(
                self.model.user_id == user_id,
                self.model.entitlement_code == entitlement_code,
                self.model.scope_key == scope_key,
                self.model.remaining_amount > 0,
                *self._valid_clauses(ts),
            )
            .order_by(
                self.model.expires_at.asc().nullslast(),
                self.model.priority.desc(),
                self.model.id.asc(),
            )
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().all()

    async def exists_any(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        entitlement_code: str,
        scope_key: str,
    ) -> bool:
        """
        判断用户是否曾经持有过该权益的额度包(不论是否已耗尽或过期)

        用于区分"配额用尽"(引导升级)与"从未拥有配额"(可走试看兜底)。

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param scope_key: 业务范围键
        :return:
        """
        stmt = (
            select(self.model.id)
            .where(
                self.model.user_id == user_id,
                self.model.entitlement_code == entitlement_code,
                self.model.scope_key == scope_key,
            )
            .limit(1)
        )
        return (await db.execute(stmt)).scalar() is not None

    async def get_by_idempotency_key(
        self,
        db: AsyncSession,
        idempotency_key: str,
    ) -> QuotaGrant | None:
        """
        通过幂等键查询额度包

        :param db: 数据库会话
        :param idempotency_key: 幂等键
        :return:
        """
        stmt = select(self.model).where(self.model.idempotency_key == idempotency_key)
        return (await db.execute(stmt)).scalars().first()

    async def get_by_ids(
        self,
        db: AsyncSession,
        ids: Sequence[int],
        *,
        for_update: bool = False,
    ) -> Sequence[QuotaGrant]:
        """
        按主键批量查询额度包(用于退款回补)

        :param db: 数据库会话
        :param ids: 额度包 ID 列表
        :param for_update: 是否加行锁
        :return:
        """
        if not ids:
            return []

        stmt = select(self.model).where(self.model.id.in_(list(ids)))
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().all()

    async def get_select(
        self,
        *,
        user_id: int | None = None,
        entitlement_code: str | None = None,
        scope_key: str | None = None,
        source: str | None = None,
        status: CommonStatus | None = None,
    ) -> Select:
        """
        分页查询语句

        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param scope_key: 业务范围键
        :param source: 额度来源
        :param status: 状态
        :return:
        """
        filters: dict[str, object] = {}
        if user_id is not None:
            filters['user_id__eq'] = user_id
        if entitlement_code is not None:
            filters['entitlement_code__eq'] = entitlement_code
        if scope_key is not None:
            filters['scope_key__eq'] = scope_key
        if source is not None:
            filters['source__eq'] = source
        if status is not None:
            filters['status__eq'] = status
        return await self.select_order('id', 'desc', **filters)


quota_grant_dao: CRUDQuotaGrant = CRUDQuotaGrant(QuotaGrant)
