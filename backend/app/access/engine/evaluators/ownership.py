#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.engine.evaluators.base import BaseEvaluator
from backend.app.access.engine.snapshot import UserGrantSnapshot
from backend.app.access.model.rule import ResourceRule
from backend.app.access.schema.engine import AccessContext, Decision, ExplanationNode


class OwnershipEvaluator(BaseEvaluator):
    """单点付费(拼团/单题购买)评估器, 预留接入点"""

    name = 'OwnershipEvaluator'

    async def evaluate(
        self,
        db: AsyncSession,
        ctx: AccessContext,
        rules: Sequence[ResourceRule],
        snapshot: UserGrantSnapshot,
        explanation: list[ExplanationNode],
    ) -> Decision | None:
        """
        当前架构未启用 user_resource_ownership 表, 直接跳过

        :param db: 数据库会话
        :param ctx: 决策上下文
        :param rules: 资源规则
        :param snapshot: 用户权益快照
        :param explanation: 决策路径累计
        :return:
        """
        self._log_pass(explanation, self.name, '单点付费未启用')
        return None
