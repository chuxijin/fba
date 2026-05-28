#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import CommonStatus, GrantMode
from backend.app.access.model.rule import ResourceRule


class CRUDResourceRule(CRUDPlus[ResourceRule]):
    """资源规则 CRUD"""

    @staticmethod
    async def _get_qbank_ancestor_ids(db: AsyncSession, *, resource_id: int) -> list[int]:
        """
        获取题库自身及父级题库 ID

        :param db: 数据库会话
        :param resource_id: 题库 ID
        :return:
        """
        from backend.app.question_bank.model import QuestionBank

        ancestor_ids: list[int] = []
        visited_ids: set[int] = set()
        current_id = resource_id

        while current_id and current_id not in visited_ids:
            visited_ids.add(current_id)
            ancestor_ids.append(current_id)

            stmt = select(QuestionBank.parent_id).where(QuestionBank.id == current_id)
            parent_id = (await db.execute(stmt)).scalar_one_or_none()
            if parent_id is None:
                break
            current_id = parent_id

        return ancestor_ids

    async def resolve_for_resource(
        self,
        db: AsyncSession,
        *,
        resource_type: str,
        resource_id: int,
        ts: datetime,
    ) -> Sequence[ResourceRule]:
        """
        解析资源在指定时刻的所有生效规则

        :param db: 数据库会话
        :param resource_type: 资源类型
        :param resource_id: 资源 ID
        :param ts: 时间点
        :return:
        """
        if resource_type == 'qbank':
            return await self._resolve_qbank_resource(db, resource_id=resource_id, ts=ts)

        stmt = (
            select(self.model)
            .where(
                self.model.resource_type == resource_type,
                self.model.resource_id == resource_id,
                self.model.status == CommonStatus.ACTIVE,
                or_(
                    self.model.valid_period.is_(None),
                    self.model.valid_period.contains(ts),
                ),
            )
            .order_by(self.model.priority.desc(), self.model.id.asc())
        )
        return (await db.execute(stmt)).scalars().all()

    async def _resolve_qbank_resource(
        self,
        db: AsyncSession,
        *,
        resource_id: int,
        ts: datetime,
    ) -> Sequence[ResourceRule]:
        """
        解析题库自身及可继承父级规则

        :param db: 数据库会话
        :param resource_id: 题库 ID
        :param ts: 时间点
        :return:
        """
        ancestor_ids = await self._get_qbank_ancestor_ids(db, resource_id=resource_id)
        if not ancestor_ids:
            return []

        inherited_ids = ancestor_ids[1:]
        resource_filters = [self.model.resource_id == resource_id]
        if inherited_ids:
            resource_filters.append(self.model.resource_id.in_(inherited_ids))

        stmt = (
            select(self.model)
            .where(
                self.model.resource_type == 'qbank',
                or_(*resource_filters),
                or_(
                    self.model.resource_id == resource_id,
                    self.model.inherit_to_children.is_(True),
                ),
                self.model.status == CommonStatus.ACTIVE,
                or_(
                    self.model.valid_period.is_(None),
                    self.model.valid_period.contains(ts),
                ),
            )
            .order_by(self.model.priority.desc(), self.model.id.asc())
        )
        return (await db.execute(stmt)).scalars().all()

    async def get_select(
        self,
        *,
        resource_type: str | None = None,
        resource_id: int | None = None,
        entitlement_code: str | None = None,
        grant_mode: GrantMode | None = None,
        status: CommonStatus | None = None,
    ) -> Select:
        """
        分页查询语句

        :param resource_type: 资源类型
        :param resource_id: 资源 ID
        :param entitlement_code: 权益编码
        :param grant_mode: 授权模式
        :param status: 状态
        :return:
        """
        filters: dict[str, object] = {}
        if resource_type is not None:
            filters['resource_type__eq'] = resource_type
        if resource_id is not None:
            filters['resource_id__eq'] = resource_id
        if entitlement_code is not None:
            filters['entitlement_code__eq'] = entitlement_code
        if grant_mode is not None:
            filters['grant_mode__eq'] = grant_mode
        if status is not None:
            filters['status__eq'] = status
        return await self.select_order('priority', 'desc', **filters)


resource_rule_dao: CRUDResourceRule = CRUDResourceRule(ResourceRule)
