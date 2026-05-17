#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import GrantMode, ReasonCode
from backend.app.access.engine.evaluators.base import BaseEvaluator
from backend.app.access.engine.snapshot import UserGrantSnapshot
from backend.app.access.model.rule import ResourceRule
from backend.app.access.schema.engine import AccessContext, Decision, ExplanationNode


class FreePassEvaluator(BaseEvaluator):
    """限时免费 / 全免规则评估器"""

    name = 'FreePassEvaluator'

    async def evaluate(
        self,
        db: AsyncSession,
        ctx: AccessContext,
        rules: Sequence[ResourceRule],
        snapshot: UserGrantSnapshot,
        explanation: list[ExplanationNode],
    ) -> Decision | None:
        """
        若存在 grant_mode=free_pass 规则, 直接放行

        :param db: 数据库会话
        :param ctx: 决策上下文
        :param rules: 资源规则
        :param snapshot: 用户权益快照
        :param explanation: 决策路径累计
        :return:
        """
        for rule in rules:
            if rule.grant_mode == GrantMode.FREE_PASS:
                self._log_allow(
                    explanation,
                    self.name,
                    '资源命中限时免费规则',
                    matched={'rule_id': rule.id, 'entitlement_code': rule.entitlement_code},
                )
                return Decision.allow(
                    reason_code=ReasonCode.FREE_PASS,
                    matched_grant=rule.entitlement_code,
                    explanation=explanation,
                )
        self._log_pass(explanation, self.name, '无限免规则')
        return None
