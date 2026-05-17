#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import CommonStatus, TemplateKind
from backend.app.access.model.template import SubscriptionTemplate, TemplatePack


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
        return await self.select_order('display_order', 'asc', **filters)


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
