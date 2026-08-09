#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CycleType, GrantMode, ReasonCode
from backend.app.access.crud.crud_quota_grant import quota_grant_dao
from backend.app.access.engine.evaluators.base import BaseEvaluator
from backend.app.access.engine.ledger import ledger_service
from backend.app.access.engine.snapshot import UserGrantSnapshot
from backend.app.access.model.rule import ResourceRule
from backend.app.access.schema.engine import AccessContext, Decision, ExplanationNode


class MeteredEvaluator(BaseEvaluator):
    """计量配额评估器

    只看额度包余额, 不查订阅 —— 订阅只是额度包的来源之一, 活动赠送、邀请奖励、
    积分兑换同样能给免费用户发放额度包, 它们在这里一视同仁。

    "曾经有过额度包但已耗尽"与"从未拥有额度"是两种不同的产品语义:
    前者应引导升级(deny QUOTA_EXHAUSTED), 后者让位给试看策略兜底(返回 None)。
    """

    name = 'MeteredEvaluator'

    async def evaluate(
        self,
        db: AsyncSession,
        ctx: AccessContext,
        rules: Sequence[ResourceRule],
        snapshot: UserGrantSnapshot,
        explanation: list[ExplanationNode],
    ) -> Decision | None:
        """
        对 grant_mode=metered 的规则按额度包余额判定并扣减

        :param db: 数据库会话
        :param ctx: 决策上下文
        :param rules: 资源规则
        :param snapshot: 用户权益快照
        :param explanation: 决策路径累计
        :return:
        """
        metered_rules = [rule for rule in rules if rule.grant_mode == GrantMode.METERED]
        if not metered_rules:
            self._log_pass(explanation, self.name, '无计量配额规则')
            return None

        exhausted = False
        for rule in metered_rules:
            cycle_type = (rule.metadata_ or {}).get('cycle_type', CycleType.MONTHLY)

            if not ctx.consume_trial:
                balance = await ledger_service.get_balance(
                    db,
                    user_id=ctx.user_id,
                    entitlement_code=rule.entitlement_code,
                    scope_key=ctx.scope_key,
                    cycle_type=cycle_type,
                    ts=ctx.request_ts,
                )
                if balance > 0:
                    self._log_allow(
                        explanation,
                        self.name,
                        '计量配额充足(预检不扣减)',
                        matched={'entitlement_code': rule.entitlement_code, 'balance': balance},
                    )
                    return Decision.allow(
                        reason_code=ReasonCode.METERED_CONSUMED,
                        matched_grant=rule.entitlement_code,
                        explanation=explanation,
                    )
            else:
                source_ref = ctx.source_ref or f'{ctx.resource_type}:{ctx.resource_id}'
                entry = await ledger_service.try_consume(
                    db,
                    user_id=ctx.user_id,
                    entitlement_code=rule.entitlement_code,
                    amount=1,
                    cycle_type=cycle_type,
                    scope_key=ctx.scope_key,
                    source='metered',
                    source_ref=source_ref,
                    idempotency_key=f'metered:{ctx.user_id}:{rule.entitlement_code}:{ctx.scope_key}:{source_ref}',
                    reason='metered access',
                    ts=ctx.request_ts,
                )
                if entry is not None:
                    self._log_allow(
                        explanation,
                        self.name,
                        '计量配额扣减成功',
                        matched={
                            'entitlement_code': rule.entitlement_code,
                            'ledger_id': entry.id,
                            'balance_after': entry.balance_after,
                        },
                    )
                    return Decision.allow(
                        reason_code=ReasonCode.METERED_CONSUMED,
                        matched_grant=rule.entitlement_code,
                        consumed_ledger_id=entry.id,
                        explanation=explanation,
                    )

            if await quota_grant_dao.exists_any(
                db,
                user_id=ctx.user_id,
                entitlement_code=rule.entitlement_code,
                scope_key=ctx.scope_key,
            ):
                exhausted = True

        if exhausted:
            self._log_pass(explanation, self.name, '计量配额已耗尽')
            return Decision.deny(reason_code=ReasonCode.QUOTA_EXHAUSTED, explanation=explanation)

        self._log_pass(explanation, self.name, '用户从未持有该计量配额, 让位给试看策略')
        return None
