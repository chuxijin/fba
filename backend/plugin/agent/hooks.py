from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.common.log import log
from backend.core.conf import settings
from backend.plugin.agent.service.coach_service import shenlun_coach_service
from backend.plugin.agent.service.shenlun_service import shenlun_grading_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用启动时恢复未完成的申论批改任务。"""
    try:
        recovered = await shenlun_grading_service.recover_pending_runs()
        if recovered:
            log.info(f'申论批改 Agent 已调度 {recovered} 个恢复任务')
    except Exception as error:
        log.exception(f'申论批改 Agent 启动恢复失败: {error}')
    if getattr(settings, 'AGENT_SHENLUN_COACH_ENABLED', False):
        try:
            recovered = await shenlun_coach_service.recover_pending_runs()
            if recovered:
                log.info(f'申论教练 Agent 已调度 {recovered} 个恢复任务')
        except Exception as error:
            log.exception(f'申论教练 Agent 启动恢复失败: {error}')
    try:
        yield
    finally:
        if getattr(settings, 'AGENT_SHENLUN_COACH_ENABLED', False):
            await shenlun_coach_service.shutdown()
        await shenlun_grading_service.shutdown()
