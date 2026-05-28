#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.plugin.agents.schema import GradingState
from backend.plugin.agents.service.common.llm import LLMCallStats, LLMClient
from backend.plugin.agents.service.common.prompts import PromptLoader
from backend.plugin.agents.service.common.streaming import EventBus


class NodeContractError(RuntimeError):
    """节点前置/后置 contract 校验失败, 让 failure 早暴露不污染下游"""


@dataclass
class NodeContext:
    """节点执行上下文"""

    state: GradingState
    db: AsyncSession
    event_bus: EventBus
    llm: LLMClient
    prompts: PromptLoader
    _llm_stats_by_task: dict[asyncio.Task[Any], LLMCallStats] = field(default_factory=dict, repr=False)

    @property
    def last_llm_stats(self) -> LLMCallStats | None:
        """获取当前执行任务的 LLM 调用统计"""
        task = asyncio.current_task()
        if task is None:
            return None
        return self._llm_stats_by_task.get(task)

    @last_llm_stats.setter
    def last_llm_stats(self, value: LLMCallStats | None) -> None:
        """
        记录当前执行任务的 LLM 调用统计

        :param value: LLM 调用统计
        :return:
        """
        task = asyncio.current_task()
        if task is None:
            return
        if value is None:
            self._llm_stats_by_task.pop(task, None)
            return
        self._llm_stats_by_task[task] = value
