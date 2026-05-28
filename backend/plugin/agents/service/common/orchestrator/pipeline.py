#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import time

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from backend.plugin.agents.schema import (
    AgentEvent,
    AgentTraceItem,
    AgentType,
    EventType,
    SectionName,
)
from backend.plugin.agents.service.common.orchestrator.context import NodeContext
from backend.utils.timezone import timezone

NodeFunc = Callable[[NodeContext], Awaitable[None]]
CheckpointFunc = Callable[[str, float, dict[str, Any]], Awaitable[None]]


@dataclass
class Node:
    """单个执行节点"""

    name: str
    stage: str
    func: NodeFunc
    section: SectionName | None = None


@dataclass
class ParallelGroup:
    """并行节点组"""

    nodes: list[Node] = field(default_factory=list)


PipelineStep = Node | ParallelGroup


class Pipeline:
    """Agent 编排 pipeline"""

    def __init__(
        self,
        agent_type: AgentType,
        steps: list[PipelineStep],
        on_checkpoint: CheckpointFunc | None = None,
    ) -> None:
        self.agent_type = agent_type
        self.steps = steps
        self._on_checkpoint = on_checkpoint

    async def run(self, ctx: NodeContext) -> None:
        """
        顺序执行所有步骤, 自动推送事件与记录轨迹

        :param ctx: 节点上下文
        :return:
        """
        total = max(len(self.steps), 1)
        try:
            for index, step in enumerate(self.steps):
                progress_after = (index + 1) / total
                if isinstance(step, Node):
                    await self._run_node(ctx, step, progress_after)
                else:
                    await asyncio.gather(
                        *[self._run_node(ctx, node, progress_after) for node in step.nodes]
                    )
            await self._publish(
                ctx,
                EventType.completed,
                progress=1.0,
                message='批改完成',
            )
        except Exception as e:
            await self._publish(
                ctx,
                EventType.failed,
                progress=0.0,
                message=f'批改失败: {e!s}',
                error_code=type(e).__name__,
            )
            raise

    async def _run_node(self, ctx: NodeContext, node: Node, progress: float) -> None:
        """
        执行单节点并推送相关事件

        :param ctx: 节点上下文
        :param node: 节点
        :param progress: 整体进度
        :return:
        """
        started = timezone.now()
        started_perf = time.perf_counter()

        await self._publish(
            ctx,
            EventType.stage_start,
            stage=node.stage,
            progress=progress,
            message=f'开始: {node.name}',
        )

        await node.func(ctx)

        duration_ms = int((time.perf_counter() - started_perf) * 1000)
        finished = timezone.now()

        # 从 NodeContext 读取 LLM 调用统计
        llm_stats = ctx.last_llm_stats
        trace_item = AgentTraceItem(
            agent=node.name,
            stage=node.stage,
            started_at=started,
            finished_at=finished,
            duration_ms=duration_ms,
            summary=f'{node.name} 完成',
        )
        if llm_stats is not None:
            trace_item.model = llm_stats.model
            trace_item.tokens_in = llm_stats.tokens_in
            trace_item.tokens_out = llm_stats.tokens_out

        ctx.state.traces.append(trace_item)
        ctx.last_llm_stats = None  # 重置, 避免下一个节点误读

        if node.section is not None:
            section_obj = getattr(ctx.state, node.section.value, None)
            if section_obj is not None:
                section_data = (
                    section_obj.model_dump() if hasattr(section_obj, 'model_dump') else section_obj
                )
                await self._publish(
                    ctx,
                    EventType.section_ready,
                    stage=node.stage,
                    progress=progress,
                    section_name=node.section,
                    section_data=section_data,
                )

        await self._publish(
            ctx,
            EventType.stage_finish,
            stage=node.stage,
            progress=progress,
            message=f'完成: {node.name}',
        )

        # 落库中间状态, 用于崩溃恢复
        if self._on_checkpoint is not None:
            snapshot = self._build_snapshot(ctx)
            await self._on_checkpoint(node.stage, progress, snapshot)

    async def _publish(
        self,
        ctx: NodeContext,
        event_type: EventType,
        *,
        stage: str = '',
        progress: float = 0.0,
        section_name: SectionName | None = None,
        section_data: dict[str, Any] | None = None,
        message: str = '',
        error_code: str | None = None,
    ) -> None:
        """
        构造并推送事件

        :param ctx: 节点上下文
        :param event_type: 事件类型
        :param stage: 当前阶段
        :param progress: 进度
        :param section_name: section 名
        :param section_data: section 数据
        :param message: 消息
        :param error_code: 错误码
        :return:
        """
        event = AgentEvent(
            event_type=event_type,
            task_id=ctx.state.task_id,
            agent_type=self.agent_type,
            stage=stage,
            progress=progress,
            section_name=section_name,
            section_data=section_data,
            message=message,
            error_code=error_code,
        )
        await ctx.event_bus.publish(event)

    @staticmethod
    def _build_snapshot(ctx: NodeContext) -> dict[str, Any]:
        """构建当前已完成的 section 快照, 用于崩溃恢复"""
        snapshot: dict[str, Any] = {}
        for section_name in SectionName:
            section_obj = getattr(ctx.state, section_name.value, None)
            if section_obj is not None and hasattr(section_obj, 'model_dump'):
                snapshot[section_name.value] = section_obj.model_dump()
        snapshot['traces'] = [t.model_dump() for t in ctx.state.traces]
        return snapshot
