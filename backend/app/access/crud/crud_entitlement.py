#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import CommonStatus, EntitlementCategory, EntitlementVerb
from backend.app.access.model.entitlement import Entitlement


class CRUDEntitlement(CRUDPlus[Entitlement]):
    """权益 CRUD"""

    async def get_by_code(self, db: AsyncSession, code: str) -> Entitlement | None:
        """
        按编码获取

        :param db: 数据库会话
        :param code: 权益编码
        :return:
        """
        stmt = select(self.model).where(self.model.code == code)
        return (await db.execute(stmt)).scalars().first()

    async def get_by_codes(self, db: AsyncSession, codes: list[str]) -> Sequence[Entitlement]:
        """
        按编码批量获取

        :param db: 数据库会话
        :param codes: 权益编码列表
        :return:
        """
        if not codes:
            return []
        stmt = select(self.model).where(self.model.code.in_(codes))
        return (await db.execute(stmt)).scalars().all()

    async def get_select(
        self,
        *,
        keyword: str | None = None,
        category: EntitlementCategory | None = None,
        verb: EntitlementVerb | None = None,
        domain_id: int | None = None,
        resource_type: str | None = None,
        status: CommonStatus | None = None,
    ) -> Select:
        """
        分页查询语句

        :param keyword: 关键字
        :param category: 分类
        :param verb: 动作
        :param domain_id: 领域 ID
        :param resource_type: 资源类型
        :param status: 状态
        :return:
        """
        filters: dict[str, object] = {}
        if keyword:
            filters['name__like'] = f'%{keyword}%'
        if category is not None:
            filters['category__eq'] = category
        if verb is not None:
            filters['verb__eq'] = verb
        if domain_id is not None:
            filters['domain_id__eq'] = domain_id
        if resource_type is not None:
            filters['resource_type__eq'] = resource_type
        if status is not None:
            filters['status__eq'] = status
        return await self.select_order('id', 'desc', **filters)


entitlement_dao: CRUDEntitlement = CRUDEntitlement(Entitlement)
