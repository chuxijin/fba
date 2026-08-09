#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import CommonStatus
from backend.app.access.model.pack import EntitlementPack, PackItem


class CRUDEntitlementPack(CRUDPlus[EntitlementPack]):
    """权益包 CRUD"""

    async def get_by_code(self, db: AsyncSession, code: str) -> EntitlementPack | None:
        """
        按编码获取

        :param db: 数据库会话
        :param code: 包编码
        :return:
        """
        stmt = select(self.model).where(self.model.code == code)
        return (await db.execute(stmt)).scalars().first()

    async def get_by_codes(self, db: AsyncSession, codes: list[str]) -> Sequence[EntitlementPack]:
        """
        按编码批量获取

        :param db: 数据库会话
        :param codes: 包编码列表
        :return:
        """
        if not codes:
            return []
        stmt = select(self.model).where(self.model.code.in_(codes))
        return (await db.execute(stmt)).scalars().all()

    async def get_select(
        self,
        *,
        domain_id: int | None = None,
        status: CommonStatus | None = None,
    ) -> Select:
        """
        分页查询语句

        :param domain_id: 领域 ID
        :param status: 状态
        :return:
        """
        filters: dict[str, object] = {}
        if domain_id is not None:
            filters['domain_id__eq'] = domain_id
        if status is not None:
            filters['status__eq'] = status
        return await self.select_order('id', 'desc', **filters)


class CRUDPackItem(CRUDPlus[PackItem]):
    """权益包成员 CRUD"""

    async def get_by_pack(self, db: AsyncSession, pack_id: int) -> Sequence[PackItem]:
        """
        按包 ID 列出成员

        :param db: 数据库会话
        :param pack_id: 包 ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.pack_id == pack_id, self.model.status == CommonStatus.ACTIVE)
            .order_by(self.model.id.asc())
        )
        return (await db.execute(stmt)).scalars().all()

    async def get_by_packs(self, db: AsyncSession, pack_ids: list[int]) -> Sequence[PackItem]:
        """
        按包 ID 批量列出成员

        :param db: 数据库会话
        :param pack_ids: 包 ID 列表
        :return:
        """
        if not pack_ids:
            return []
        stmt = (
            select(self.model)
            .where(self.model.pack_id.in_(pack_ids), self.model.status == CommonStatus.ACTIVE)
            .order_by(self.model.id.asc())
        )
        return (await db.execute(stmt)).scalars().all()

    async def delete_by_pack(self, db: AsyncSession, pack_id: int) -> int:
        """
        清空指定包的所有成员

        :param db: 数据库会话
        :param pack_id: 包 ID
        :return:
        """
        result = await db.execute(delete(self.model).where(self.model.pack_id == pack_id))
        return result.rowcount or 0


entitlement_pack_dao: CRUDEntitlementPack = CRUDEntitlementPack(EntitlementPack)
pack_item_dao: CRUDPackItem = CRUDPackItem(PackItem)
