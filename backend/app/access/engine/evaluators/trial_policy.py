#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CycleType, ReasonCode, TrialMode
from backend.app.access.engine.cycle import build_cycle_end, build_cycle_key
from backend.app.access.engine.evaluators.base import BaseEvaluator
from backend.app.access.engine.snapshot import UserGrantSnapshot
from backend.app.access.engine.trial_counter import trial_counter_service
from backend.app.access.model.rule import ResourceRule
from backend.app.access.schema.engine import AccessContext, Decision, ExplanationNode
from backend.common.log import log
from backend.database.redis import redis_client
from backend.utils.timezone import timezone

_TRIAL_COUNTER_PREFIX = 'access:trial'


class TrialPolicyEvaluator(BaseEvaluator):
    """试看策略评估器(责任链兜底)

    试看是"未付费用户的体验策略", 不是权益凭证 —— 因此这里既不查 entitlement,
    也不写 quota_ledger。ordinal / fraction / excerpt 三种模式完全无状态;
    daily_count 用 Redis 匿名计数器, 计数丢失最坏只是多给用户几次体验。
    """

    name = 'TrialPolicyEvaluator'

    async def evaluate(
        self,
        db: AsyncSession,
        ctx: AccessContext,
        rules: Sequence[ResourceRule],
        snapshot: UserGrantSnapshot,
        explanation: list[ExplanationNode],
    ) -> Decision | None:
        """
        用户未命中任何权益时, 按资源规则上的试看策略决定是否降级放行

        :param db: 数据库会话
        :param ctx: 决策上下文
        :param rules: 资源规则
        :param snapshot: 用户权益快照
        :param explanation: 决策路径累计
        :return:
        """
        if not ctx.allow_trial:
            self._log_pass(explanation, self.name, '当前业务不允许试看')
            return None

        trial_rules = [rule for rule in rules if rule.trial_policy]
        if not trial_rules:
            self._log_pass(explanation, self.name, '资源未配置试看策略')
            return None

        evaluated = False
        for rule in trial_rules:
            decision = await self._apply(ctx, rule, explanation)
            if decision is None:
                continue
            evaluated = True
            if decision.allowed:
                return decision

        if not evaluated:
            self._log_pass(explanation, self.name, '试看策略缺少判定所需的上下文')
            return None

        self._log_pass(explanation, self.name, '试看额度已用尽')
        return Decision.deny(reason_code=ReasonCode.TRIAL_EXHAUSTED, explanation=explanation)

    async def _apply(
        self,
        ctx: AccessContext,
        rule: ResourceRule,
        explanation: list[ExplanationNode],
    ) -> Decision | None:
        """
        应用单条规则的试看策略

        :param ctx: 决策上下文
        :param rule: 资源规则
        :param explanation: 决策路径累计
        :return: None 表示该策略无法判定(缺少上下文), 交给下一条
        """
        policy = rule.trial_policy or {}
        mode = policy.get('mode')

        if mode == TrialMode.EXCERPT:
            chars = int(policy.get('chars') or 0)
            self._log_allow(
                explanation,
                self.name,
                f'按摘录试看, 可见前 {chars} 字',
                matched={'rule_id': rule.id, 'mode': mode, 'chars': chars},
            )
            return Decision.allow(
                reason_code=ReasonCode.TRIAL_POLICY,
                matched_grant=rule.entitlement_code,
                trial_mode=mode,
                trial_excerpt_chars=chars,
                explanation=explanation,
            )

        if mode == TrialMode.ORDINAL:
            if ctx.sub_resource_ordinal is None:
                return None
            limit = int(policy.get('limit') or 0)
            return self._ordinal_decision(
                ctx=ctx,
                rule=rule,
                mode=mode,
                threshold=limit,
                explanation=explanation,
                allow_reason=f'按序位试看, 前 {limit} 个子资源免费',
            )

        if mode == TrialMode.FRACTION:
            if ctx.sub_resource_ordinal is None or not ctx.sub_resource_total:
                return None
            ratio = float(policy.get('ratio') or 0)
            threshold = int(ctx.sub_resource_total * ratio)
            return self._ordinal_decision(
                ctx=ctx,
                rule=rule,
                mode=mode,
                threshold=threshold,
                explanation=explanation,
                allow_reason=f'按比例试看, 前 {threshold} 个子资源免费',
            )

        if mode == TrialMode.DAILY_COUNT:
            return await self._daily_count_decision(ctx, rule, explanation)

        log.warning(f'未知试看模式: rule_id={rule.id}, mode={mode}')
        return None

    def _ordinal_decision(
        self,
        *,
        ctx: AccessContext,
        rule: ResourceRule,
        mode: str,
        threshold: int,
        explanation: list[ExplanationNode],
        allow_reason: str,
    ) -> Decision:
        """
        按序位阈值判定(ordinal 与 fraction 共用)

        :param ctx: 决策上下文
        :param rule: 资源规则
        :param mode: 试看模式
        :param threshold: 放行的序位上界(不含)
        :param explanation: 决策路径累计
        :param allow_reason: 放行原因描述
        :return:
        """
        ordinal = int(ctx.sub_resource_ordinal or 0)
        if ordinal < threshold:
            self._log_allow(
                explanation,
                self.name,
                allow_reason,
                matched={'rule_id': rule.id, 'mode': mode, 'ordinal': ordinal, 'threshold': threshold},
            )
            return Decision.allow(
                reason_code=ReasonCode.TRIAL_POLICY,
                matched_grant=rule.entitlement_code,
                trial_mode=mode,
                explanation=explanation,
            )
        return Decision.deny(reason_code=ReasonCode.TRIAL_EXHAUSTED, explanation=explanation)

    async def _daily_count_decision(
        self,
        ctx: AccessContext,
        rule: ResourceRule,
        explanation: list[ExplanationNode],
    ) -> Decision:
        """
        按日计数判定(匿名计数器, 不落权益也不落账本)

        :param ctx: 决策上下文
        :param rule: 资源规则
        :param explanation: 决策路径累计
        :return:
        """
        policy = rule.trial_policy or {}
        limit = int(policy.get('limit') or 0)
        now = ctx.request_ts or timezone.now()
        cache_key = (
            f'{_TRIAL_COUNTER_PREFIX}:{ctx.user_id}:{rule.resource_type}:'
            f'{rule.resource_id}:{rule.entitlement_code}:{build_cycle_key(CycleType.DAILY, now)}'
        )
        cycle_end = build_cycle_end(CycleType.DAILY, now)
        ttl = max(int((cycle_end - now).total_seconds()), 1) if cycle_end else 86400
        idempotency_key: str | None = None

        try:
            if ctx.consume_trial:
                if ctx.source_ref:
                    used, allowed, idempotency_key = await trial_counter_service.consume_once(
                        counter_key=cache_key,
                        source_ref=ctx.source_ref,
                        ttl=ttl,
                        limit=limit,
                    )
                    if not allowed:
                        return Decision.deny(reason_code=ReasonCode.TRIAL_EXHAUSTED, explanation=explanation)
                else:
                    used = int(await redis_client.incr(cache_key))
                    if used == 1:
                        await redis_client.expire(cache_key, ttl)
            else:
                used = int(await redis_client.get(cache_key) or 0) + 1
        except Exception as exc:
            # 计数器不可用时放行, 试看多给几次远好过把付费引导变成硬故障
            log.warning(f'试看计数器不可用, 降级放行: key={cache_key}, error={exc!s}')
            self._log_allow(
                explanation,
                self.name,
                '试看计数器不可用, 降级放行',
                matched={'rule_id': rule.id, 'mode': TrialMode.DAILY_COUNT.value},
            )
            return Decision.allow(
                reason_code=ReasonCode.TRIAL_POLICY,
                matched_grant=rule.entitlement_code,
                trial_mode=TrialMode.DAILY_COUNT.value,
                explanation=explanation,
            )

        if used <= limit:
            self._log_allow(
                explanation,
                self.name,
                f'按日试看, 今日第 {used}/{limit} 次',
                matched={'rule_id': rule.id, 'mode': TrialMode.DAILY_COUNT.value, 'used': used, 'limit': limit},
            )
            return Decision.allow(
                reason_code=ReasonCode.TRIAL_POLICY,
                matched_grant=rule.entitlement_code,
                trial_mode=TrialMode.DAILY_COUNT.value,
                trial_counter_key=cache_key if idempotency_key else None,
                trial_idempotency_key=idempotency_key,
                explanation=explanation,
            )
        return Decision.deny(reason_code=ReasonCode.TRIAL_EXHAUSTED, explanation=explanation)
