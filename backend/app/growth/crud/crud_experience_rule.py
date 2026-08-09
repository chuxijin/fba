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
        cycle_day: int | None = None,
        held_entitlement_codes: set[str] | None = None,
    ) -> ExperienceRule | None:
        """
        匹配当前最适用的经验规则

        规则可声明 required_entitlement_code 做差异化奖励(如会员双倍经验)。
        用它而不是硬编码的 VIP/SVIP 枚举, 是为了和"权益自由组合"的售卖模型保持一致 ——
        运营新增一个档位不需要改代码。

        :param db: 数据库会话
        :param event_code: 事件编码
        :param cycle_day: 周期第几天
        :param held_entitlement_codes: 用户当前持有的权益编码集合
        :return:
        """
        held = held_entitlement_codes or set()
        stmt = (
            select(self.model)
            .where(self.model.event_code == event_code, self.model.status == 1)
            .order_by(self.model.sort.asc(), self.model.id.asc())
        )
        rows = (await db.execute(stmt)).scalars().all()

        for rule in rows:
            if rule.cycle_day is not None and rule.cycle_day != cycle_day:
                continue
            if rule.required_entitlement_code and rule.required_entitlement_code not in held:
                continue
            return rule
        return None

    async def get_select(
        self,
        *,
        event_code: str | None = None,
        required_entitlement_code: str | None = None,
        status: int | None = None,
    ) -> Select:
        """
        获取分页查询语句

        :param event_code: 事件编码
        :param required_entitlement_code: 生效所需权益编码
        :param status: 状态
        :return:
        """
        filters: dict[str, object] = {}
        if event_code is not None:
            filters['event_code__eq'] = event_code
        if required_entitlement_code is not None:
            filters['required_entitlement_code__eq'] = required_entitlement_code
        if status is not None:
            filters['status__eq'] = status
        return await self.select_order('sort', 'asc', **filters)


experience_rule_dao: CRUDExperienceRule = CRUDExperienceRule(ExperienceRule)
