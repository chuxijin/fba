#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import DecisionKind, ReasonCode
from backend.app.access.engine.evaluators import DEFAULT_EVALUATORS, BaseEvaluator
from backend.app.access.engine.resolver import rule_resolver
from backend.app.access.engine.snapshot import snapshot_service
from backend.app.access.model.decision import DecisionLog
from backend.app.access.schema.engine import AccessContext, Decision, ExplanationNode
from backend.utils.timezone import timezone


class AccessDecisionEngine:
    """权益决策引擎(责任链)"""

    def __init__(self, evaluators: list[BaseEvaluator] | None = None) -> None:
        self._evaluators = evaluators if evaluators is not None else DEFAULT_EVALUATORS

    async def decide(self, db: AsyncSession, ctx: AccessContext) -> Decision:
        """
        发起一次权益决策

        :param db: 数据库会话
        :param ctx: 决策上下文
        :return:
        """
        request_ts = ctx.request_ts or timezone.now()
        if ctx.request_ts is None:
            ctx = ctx.model_copy(update={'request_ts': request_ts})

        explanation: list[ExplanationNode] = []

        rules = await rule_resolver.resolve(
            db,
            resource_type=ctx.resource_type,
            resource_id=ctx.resource_id,
            ts=request_ts,
            audience_attrs=ctx.audience_attrs,
        )
        if not rules:
            explanation.append(
                ExplanationNode(
                    evaluator='RuleResolver',
                    outcome='allow',
                    reason='资源无任何规则, 视为公开',
                )
            )
            decision = Decision.allow(
                reason_code=ReasonCode.FREE_RESOURCE,
                explanation=explanation,
            )
            await self._finalize(db, ctx, decision)
            return decision

        snapshot = await snapshot_service.load(db, user_id=ctx.user_id, ts=request_ts)

        for evaluator in self._evaluators:
            result = await evaluator.evaluate(db, ctx, rules, snapshot, explanation)
            if result is not None:
                await self._finalize(db, ctx, result)
                return result

        decision = Decision.deny(
            reason_code=ReasonCode.NO_MATCHING_GRANT,
            explanation=explanation,
        )
        await self._finalize(db, ctx, decision)
        return decision

    async def _finalize(self, db: AsyncSession, ctx: AccessContext, decision: Decision) -> None:
        """
        终态处理: 决策日志(仅 deny 路径写入)

        :param db: 数据库会话
        :param ctx: 决策上下文
        :param decision: 决策结果
        :return:
        """
        if decision.decision != DecisionKind.DENY:
            return
        log = DecisionLog(
            user_id=ctx.user_id,
            resource_type=ctx.resource_type,
            resource_id=ctx.resource_id,
            action=ctx.action,
            decision=decision.decision,
            reason_code=decision.reason_code,
            matched_grant=decision.matched_grant,
            context={
                'consume_trial': ctx.consume_trial,
                'audience_attrs': ctx.audience_attrs,
                'explanation': [node.model_dump() for node in decision.explanation],
            },
        )
        db.add(log)


access_decision_engine: AccessDecisionEngine = AccessDecisionEngine()
