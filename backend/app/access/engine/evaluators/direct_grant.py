#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import GrantMode, ReasonCode
from backend.app.access.engine.evaluators.base import BaseEvaluator
from backend.app.access.engine.snapshot import UserGrantSnapshot
from backend.app.access.model.rule import ResourceRule
from backend.app.access.schema.engine import AccessContext, Decision, ExplanationNode


class DirectGrantEvaluator(BaseEvaluator):
    """直接授予评估器(运营补偿/活动赠送)"""

    name = 'DirectGrantEvaluator'

    async def evaluate(
        self,
        db: AsyncSession,
        ctx: AccessContext,
        rules: Sequence[ResourceRule],
        snapshot: UserGrantSnapshot,
        explanation: list[ExplanationNode],
    ) -> Decision | None:
        """
        若用户拥有任一 access 规则对应权益的直接授予, 即放行

        :param db: 数据库会话
        :param ctx: 决策上下文
        :param rules: 资源规则
        :param snapshot: 用户权益快照
        :param explanation: 决策路径累计
        :return:
        """
        for rule in rules:
            if rule.grant_mode != GrantMode.ACCESS:
                continue
            if snapshot.has_direct_grant(rule.entitlement_code):
                self._log_allow(
                    explanation,
                    self.name,
                    '直接授予命中权益',
                    matched={'entitlement_code': rule.entitlement_code, 'rule_id': rule.id},
                )
                return Decision.allow(
                    reason_code=ReasonCode.DIRECT_GRANT,
                    matched_grant=rule.entitlement_code,
                    explanation=explanation,
                )
        self._log_pass(explanation, self.name, '无匹配的直接授予')
        return None
