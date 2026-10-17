#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import CommonStatus, TemplateKind
from backend.app.access.model.template import SubscriptionTemplate, TemplatePack
from backend.app.access.model.tier import MembershipTier
from backend.utils.timezone import timezone


class CRUDSubscriptionTemplate(CRUDPlus[SubscriptionTemplate]):
    """订阅模板 CRUD"""

    async def get_by_code(self, db: AsyncSession, code: str) -> SubscriptionTemplate | None:
        """
        按编码获取

        :param db: 数据库会话
        :param code: 模板编码
        :return:
        """
        stmt = select(self.model).where(self.model.code == code)
        return (await db.execute(stmt)).scalars().first()

    async def get_select(
        self,
        *,
        kind: TemplateKind | None = None,
        status: CommonStatus | None = None,
    ) -> Select:
        """
        分页查询语句

        :param kind: 模板类型
        :param status: 状态
        :return:
        """
        filters: dict[str, object] = {}
        if kind is not None:
            filters['kind__eq'] = kind
        if status is not None:
            filters['status__eq'] = status
        stmt = await self.select_order('display_order', 'asc', **filters)
        return stmt.where(~self.model.code.startswith('GBS_'))

    async def get_sale_catalog(self, db: AsyncSession) -> Sequence[SubscriptionTemplate]:
        """公开目录只包含当前可展示的标准/组合套餐，保留免费基础套餐"""
        stmt = (
            select(self.model)
            .join(MembershipTier, self.model.tier_id == MembershipTier.id)
            .where(
                self.model.status == CommonStatus.ACTIVE,
                self.model.kind.in_([TemplateKind.STANDARD, TemplateKind.BUNDLE]),
                self.model.price_cents >= 0,
                ~self.model.code.startswith('GBS_'),
                MembershipTier.status == CommonStatus.ACTIVE,
                or_(self.model.price_cents > 0, MembershipTier.is_paid.is_(False)),
                or_(self.model.sale_period.is_(None), self.model.sale_period.contains(timezone.now())),
            )
            .order_by(self.model.display_order.asc(), self.model.id.asc())
        )
        return (await db.execute(stmt)).scalars().all()


class CRUDTemplatePack(CRUDPlus[TemplatePack]):
    """模板-包关联 CRUD"""

    async def get_by_template(self, db: AsyncSession, template_id: int) -> Sequence[TemplatePack]:
        """
        按模板 ID 获取关联

        :param db: 数据库会话
        :param template_id: 模板 ID
        :return:
        """
        stmt = select(self.model).where(self.model.template_id == template_id)
        return (await db.execute(stmt)).scalars().all()

    async def get_by_templates(self, db: AsyncSession, template_ids: list[int]) -> Sequence[TemplatePack]:
        """
        按模板 ID 批量获取关联

        :param db: 数据库会话
        :param template_ids: 模板 ID 列表
        :return:
        """
        if not template_ids:
            return []
        stmt = select(self.model).where(self.model.template_id.in_(template_ids))
        return (await db.execute(stmt)).scalars().all()

    async def delete_by_template(self, db: AsyncSession, template_id: int) -> int:
        """
        清空指定模板的所有关联

        :param db: 数据库会话
        :param template_id: 模板 ID
        :return:
        """
        result = await db.execute(delete(self.model).where(self.model.template_id == template_id))
        return result.rowcount or 0


subscription_template_dao: CRUDSubscriptionTemplate = CRUDSubscriptionTemplate(SubscriptionTemplate)
template_pack_dao: CRUDTemplatePack = CRUDTemplatePack(TemplatePack)
