#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.membership.model.experience_rule import MembershipExperienceRule


class CRUDMembershipExperienceRule(CRUDPlus[MembershipExperienceRule]):
    """会员经验规则数据库操作类"""

    async def get_select(
        self,
        *,
        event_code: str | None = None,
        family_code: str | None = None,
        status: int | None = None,
    ) -> Select:
        """
        获取经验规则分页查询语句

        :param event_code: 事件编码
        :param family_code: 等级族群
        :param status: 状态
        :return:
        """
        filters = {}
        if event_code is not None:
            filters['event_code__eq'] = event_code
        if family_code is not None:
            filters['family_code__eq'] = family_code
        if status is not None:
            filters['status__eq'] = status
        return await self.select_order('sort', 'asc', **filters)

    async def get_active_rule(
        self,
        db: AsyncSession,
        *,
        event_code: str,
        family_code: str | None = None,
        cycle_day: int | None = None,
    ) -> MembershipExperienceRule | None:
        """
        获取匹配的启用经验规则

        :param db: 数据库会话
        :param event_code: 事件编码
        :param family_code: 等级族群
        :param cycle_day: 周期第几天
        :return:
        """
        if family_code:
            exact_rule = await self._get_rule(
                db,
                event_code=event_code,
                family_code=family_code,
                cycle_day=cycle_day,
            )
            if exact_rule:
                return exact_rule

        return await self._get_rule(
            db,
            event_code=event_code,
            family_code=None,
            cycle_day=cycle_day,
        )

    async def _get_rule(
        self,
        db: AsyncSession,
        *,
        event_code: str,
        family_code: str | None,
        cycle_day: int | None,
    ) -> MembershipExperienceRule | None:
        """
        按精确条件获取经验规则

        :param db: 数据库会话
        :param event_code: 事件编码
        :param family_code: 等级族群
        :param cycle_day: 周期第几天
        :return:
        """
        stmt = select(self.model).where(
            self.model.event_code == event_code,
            self.model.status == 1,
        )
        if family_code is None:
            stmt = stmt.where(self.model.family_code.is_(None))
        else:
            stmt = stmt.where(self.model.family_code == family_code)

        if cycle_day is None:
            stmt = stmt.where(self.model.cycle_day.is_(None))
        else:
            stmt = stmt.where(self.model.cycle_day == cycle_day)

        stmt = stmt.order_by(self.model.sort.asc(), self.model.id.asc()).limit(1)
        result = await db.execute(stmt)
        return result.scalars().first()


membership_experience_rule_dao: CRUDMembershipExperienceRule = CRUDMembershipExperienceRule(MembershipExperienceRule)
