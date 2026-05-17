#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.engine.snapshot import UserGrantSnapshot
from backend.app.access.model.rule import ResourceRule
from backend.app.access.schema.engine import AccessContext, Decision, ExplanationNode


class BaseEvaluator(ABC):
    """评估器抽象基类"""

    name: str = ''

    @abstractmethod
    async def evaluate(
        self,
        db: AsyncSession,
        ctx: AccessContext,
        rules: Sequence[ResourceRule],
        snapshot: UserGrantSnapshot,
        explanation: list[ExplanationNode],
    ) -> Decision | None:
        """
        执行评估, 返回决策或 None(让出给下一个评估器)

        :param db: 数据库会话
        :param ctx: 决策上下文
        :param rules: 当前资源生效的规则
        :param snapshot: 用户权益快照
        :param explanation: 决策路径累计
        :return:
        """
        raise NotImplementedError

    @staticmethod
    def _log_pass(explanation: list[ExplanationNode], evaluator: str, reason: str) -> None:
        """记录跳过节点"""
        explanation.append(ExplanationNode(evaluator=evaluator, outcome='pass', reason=reason))

    @staticmethod
    def _log_allow(
        explanation: list[ExplanationNode],
        evaluator: str,
        reason: str,
        matched: dict | None = None,
    ) -> None:
        """记录允许节点"""
        explanation.append(
            ExplanationNode(evaluator=evaluator, outcome='allow', reason=reason, matched=matched)
        )
