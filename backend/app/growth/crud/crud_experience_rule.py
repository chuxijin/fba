#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.growth.model.experience_rule import ExperienceRule


class CRUDExperienceRule(CRUDPlus[ExperienceRule]):
    """经验规则 CRUD"""

    async def get_active_rule(
        self,
        db: AsyncSession,
        *,
        event_code: str,
        family_code: str | None = None,
        cycle_day: int | None = None,
    ) -> ExperienceRule | None:
        """
        匹配当前最适用的经验规则

        :param db: 数据库会话
        :param event_code: 事件编码
        :param family_code: 用户族群
        :param cycle_day: 周期第几天
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.event_code == event_code, self.model.status == 1)
            .order_by(self.model.sort.asc(), self.model.id.asc())
        )
        rows = (await db.execute(stmt)).scalars().all()

        for rule in rows:
            if rule.family_code is not None and rule.family_code != family_code:
                continue
            if rule.cycle_day is not None and rule.cycle_day != cycle_day:
                continue
            return rule
        return None

    async def get_select(
        self,
        *,
        event_code: str | None = None,
        family_code: str | None = None,
        status: int | None = None,
    ) -> Select:
        """
        获取分页查询语句

        :param event_code: 事件编码
        :param family_code: 族群
        :param status: 状态
        :return:
        """
        filters: dict[str, object] = {}
        if event_code is not None:
            filters['event_code__eq'] = event_code
        if family_code is not None:
            filters['family_code__eq'] = family_code
        if status is not None:
            filters['status__eq'] = status
        return await self.select_order('sort', 'asc', **filters)


experience_rule_dao: CRUDExperienceRule = CRUDExperienceRule(ExperienceRule)
