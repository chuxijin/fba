#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Row, Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import CommonStatus, GrantSource
from backend.app.access.model.grant import DirectGrant


class CRUDDirectGrant(CRUDPlus[DirectGrant]):
    """直接授予 CRUD"""

    async def list_active_for_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        ts: datetime,
    ) -> Sequence[DirectGrant]:
        """
        列出用户在指定时刻有效的直接授予

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param ts: 时间点
        :return:
        """
        stmt = select(self.model).where(
            self.model.user_id == user_id,
            self.model.status == CommonStatus.ACTIVE,
            self.model.valid_period.contains(ts),
        )
        return (await db.execute(stmt)).scalars().all()

    async def list_active_entitlement_rows_for_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        ts: datetime,
    ) -> Sequence[Row]:
        """
        获取用户有效直接授权权益行

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param ts: 时间点
        :return:
        """
        from backend.app.access.model.entitlement import Entitlement

        stmt = (
            select(
                Entitlement.id.label('entitlement_id'),
                Entitlement.code.label('entitlement_code'),
                Entitlement.name.label('entitlement_name'),
                Entitlement.category.label('entitlement_category'),
                Entitlement.description.label('entitlement_description'),
            )
            .select_from(self.model)
            .join(Entitlement, Entitlement.code == self.model.entitlement_code)
            .where(
                self.model.user_id == user_id,
                self.model.status == CommonStatus.ACTIVE,
                self.model.valid_period.contains(ts),
            )
        )
        return (await db.execute(stmt)).all()

    async def get_select(
        self,
        *,
        user_id: int | None = None,
        entitlement_code: str | None = None,
        source: GrantSource | None = None,
        status: CommonStatus | None = None,
    ) -> Select:
        """
        分页查询语句

        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param source: 来源
        :param status: 状态
        :return:
        """
        filters: dict[str, object] = {}
        if user_id is not None:
            filters['user_id__eq'] = user_id
        if entitlement_code is not None:
            filters['entitlement_code__eq'] = entitlement_code
        if source is not None:
            filters['source__eq'] = source
        if status is not None:
            filters['status__eq'] = status
        return await self.select_order('id', 'desc', **filters)


direct_grant_dao: CRUDDirectGrant = CRUDDirectGrant(DirectGrant)
