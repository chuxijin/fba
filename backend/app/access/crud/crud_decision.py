#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.access.constants import DecisionKind
from backend.app.access.model.decision import DecisionLog


class CRUDDecisionLog(CRUDPlus[DecisionLog]):
    """决策日志 CRUD"""

    async def get_select(
        self,
        *,
        user_id: int | None = None,
        resource_type: str | None = None,
        resource_id: int | None = None,
        decision: DecisionKind | None = None,
        reason_code: str | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> Select:
        """
        分页查询语句

        :param user_id: 用户 ID
        :param resource_type: 资源类型
        :param resource_id: 资源 ID
        :param decision: 决策结果
        :param reason_code: 原因码
        :param occurred_from: 起始时间
        :param occurred_to: 结束时间
        :return:
        """
        filters: dict[str, object] = {}
        if user_id is not None:
            filters['user_id__eq'] = user_id
        if resource_type is not None:
            filters['resource_type__eq'] = resource_type
        if resource_id is not None:
            filters['resource_id__eq'] = resource_id
        if decision is not None:
            filters['decision__eq'] = decision
        if reason_code is not None:
            filters['reason_code__eq'] = reason_code
        if occurred_from is not None:
            filters['occurred_at__ge'] = occurred_from
        if occurred_to is not None:
            filters['occurred_at__le'] = occurred_to
        return await self.select_order('occurred_at', 'desc', **filters)


decision_log_dao: CRUDDecisionLog = CRUDDecisionLog(DecisionLog)
