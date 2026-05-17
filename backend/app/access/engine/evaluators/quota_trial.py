#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CycleType, GrantMode, ReasonCode
from backend.app.access.engine.evaluators.base import BaseEvaluator
from backend.app.access.engine.ledger import ledger_service
from backend.app.access.engine.snapshot import UserGrantSnapshot
from backend.app.access.model.rule import ResourceRule
from backend.app.access.schema.engine import AccessContext, Decision, ExplanationNode


class QuotaTrialEvaluator(BaseEvaluator):
    """试看配额评估器"""

    name = 'QuotaTrialEvaluator'

    async def evaluate(
        self,
        db: AsyncSession,
        ctx: AccessContext,
        rules: Sequence[ResourceRule],
        snapshot: UserGrantSnapshot,
        explanation: list[ExplanationNode],
    ) -> Decision | None:
        """
        若存在 grant_mode=trial 规则, 尝试扣减额度, 成功放行

        :param db: 数据库会话
        :param ctx: 决策上下文
        :param rules: 资源规则
        :param snapshot: 用户权益快照
        :param explanation: 决策路径累计
        :return:
        """
        trial_rules = [rule for rule in rules if rule.grant_mode == GrantMode.TRIAL]
        if not trial_rules:
            self._log_pass(explanation, self.name, '无试看规则')
            return None

        if not ctx.consume_trial:
            self._log_pass(explanation, self.name, '调用方禁止扣减试看额度')
            return Decision.deny(reason_code=ReasonCode.QUOTA_EXHAUSTED, explanation=explanation)

        for rule in trial_rules:
            source_ref = f'{ctx.resource_type}:{ctx.resource_id}'
            idempotency_key = (
                f'trial:{ctx.user_id}:{rule.entitlement_code}:{source_ref}'
            )
            entry = await ledger_service.try_consume(
                db,
                user_id=ctx.user_id,
                entitlement_code=rule.entitlement_code,
                amount=1,
                cycle_type=CycleType.MONTHLY,
                scope_key='global',
                source='trial',
                source_ref=source_ref,
                idempotency_key=idempotency_key,
                reason='trial access',
            )
            if entry is not None:
                self._log_allow(
                    explanation,
                    self.name,
                    '试看额度扣减成功',
                    matched={
                        'entitlement_code': rule.entitlement_code,
                        'ledger_id': entry.id,
                        'balance_after': entry.balance_after,
                    },
                )
                return Decision.allow(
                    reason_code=ReasonCode.QUOTA_TRIAL,
                    matched_grant=rule.entitlement_code,
                    consumed_ledger_id=entry.id,
                    explanation=explanation,
                )

        self._log_pass(explanation, self.name, '所有试看配额均已耗尽')
        return Decision.deny(
            reason_code=ReasonCode.QUOTA_EXHAUSTED,
            explanation=explanation,
        )
