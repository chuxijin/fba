#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.agents.model import AgentTask


class CRUDAgentTask(CRUDPlus[AgentTask]):
    """Agent 任务 CRUD"""

    async def create_task(
        self,
        db: AsyncSession,
        *,
        agent_type: str,
        user_id: int,
        provider_id: int,
        model_id: str,
        input_payload: dict[str, Any],
    ) -> AgentTask:
        """
        创建 Agent 任务

        :param db: 数据库会话
        :param agent_type: agent 类型
        :param user_id: 用户 ID
        :param provider_id: AI 供应商 ID
        :param model_id: 主力模型 ID
        :param input_payload: 输入参数
        :return:
        """
        task = AgentTask(
            agent_type=agent_type,
            user_id=user_id,
            provider_id=provider_id,
            model_id=model_id,
            input_payload=input_payload,
        )
        db.add(task)
        await db.flush()
        return task

    async def get(self, db: AsyncSession, pk: int) -> AgentTask | None:
        """
        获取任务

        :param db: 数据库会话
        :param pk: 任务 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def mark_running(
        self,
        db: AsyncSession,
        task: AgentTask,
        *,
        stage: str,
        progress: float = 0.0,
    ) -> None:
        """
        标记任务运行中

        :param db: 数据库会话
        :param task: 任务对象
        :param stage: 当前阶段
        :param progress: 进度
        :return:
        """
        task.status = 'running'
        task.stage = stage
        task.progress = progress
        await db.flush()

    async def update_progress(
        self,
        db: AsyncSession,
        task: AgentTask,
        *,
        stage: str | None = None,
        progress: float | None = None,
        state_snapshot: dict[str, Any] | None = None,
    ) -> None:
        """
        更新任务进度与快照

        :param db: 数据库会话
        :param task: 任务对象
        :param stage: 阶段标识
        :param progress: 进度
        :param state_snapshot: 中间快照
        :return:
        """
        if stage is not None:
            task.stage = stage
        if progress is not None:
            task.progress = progress
        if state_snapshot is not None:
            task.state_snapshot = state_snapshot
        await db.flush()

    async def mark_completed(
        self,
        db: AsyncSession,
        task: AgentTask,
        *,
        report: dict[str, Any],
        traces: list[dict[str, Any]],
        quota_consumed: bool,
    ) -> None:
        """
        标记任务完成

        :param db: 数据库会话
        :param task: 任务对象
        :param report: 最终报告
        :param traces: 执行轨迹
        :param quota_consumed: 是否已扣权益
        :return:
        """
        task.status = 'completed'
        task.stage = 'completed'
        task.progress = 1.0
        task.report = report
        task.traces = traces
        task.quota_consumed = quota_consumed
        await db.flush()

    async def mark_failed(
        self,
        db: AsyncSession,
        task: AgentTask,
        *,
        error_code: str,
        error_message: str,
        report: dict[str, Any] | None = None,
        traces: list[dict[str, Any]] | None = None,
        quota_consumed: bool = False,
    ) -> None:
        """
        标记任务失败

        :param db: 数据库会话
        :param task: 任务对象
        :param error_code: 错误码
        :param error_message: 错误信息
        :param report: 最终报告
        :param traces: 执行轨迹
        :param quota_consumed: 是否已扣权益
        :return:
        """
        task.status = 'failed'
        task.stage = 'failed'
        task.error_code = error_code
        task.error_message = error_message
        task.quota_consumed = quota_consumed
        if report is not None:
            task.report = report
        if traces is not None:
            task.traces = traces
        await db.flush()

    async def list_recent_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        limit: int = 20,
        agent_type: str | None = None,
    ) -> Sequence[AgentTask]:
        """
        按用户获取最近任务

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param limit: 数量
        :param agent_type: agent 类型过滤
        :return:
        """
        stmt = sa.select(AgentTask).where(AgentTask.user_id == user_id)
        if agent_type is not None:
            stmt = stmt.where(AgentTask.agent_type == agent_type)
        stmt = stmt.order_by(AgentTask.created_time.desc()).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()


agent_task_dao: CRUDAgentTask = CRUDAgentTask(AgentTask)
