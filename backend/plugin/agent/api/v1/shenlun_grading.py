import json

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Path, Request
from starlette.responses import StreamingResponse

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.agent.schema.grading import (
    GradingFeedbackParam,
    GradingRunRead,
    StartShenlunGradingParam,
    StartShenlunGradingResult,
)
from backend.plugin.agent.service.shenlun_service import shenlun_grading_service

router = APIRouter(dependencies=[DependsJwtAuth])


@router.post(
    '/attempts/{attempt_id}/grading',
    summary='启动申论批改 Agent',
)
async def start_shenlun_grading(
    request: Request,
    db: CurrentSessionTransaction,
    attempt_id: Annotated[int, Path(gt=0, description='题库 V2 作答事实 ID')],
    obj: StartShenlunGradingParam,
) -> ResponseSchemaModel[StartShenlunGradingResult]:
    result = await shenlun_grading_service.start(
        db=db,
        attempt_id=attempt_id,
        user_id=request.user.id,
        params=obj,
    )
    return response_base.success(data=result)


@router.get('/runs/{run_id}', summary='获取申论批改 Agent 结果')
async def get_shenlun_grading(
    request: Request,
    db: CurrentSession,
    run_id: Annotated[int, Path(gt=0, description='Agent 运行 ID')],
) -> ResponseSchemaModel[GradingRunRead]:
    result = await shenlun_grading_service.get_detail(db=db, run_id=run_id, user_id=request.user.id)
    return response_base.success(data=result)


@router.post('/runs/{run_id}/retry', summary='重试申论批改 Agent')
async def retry_shenlun_grading(
    request: Request,
    db: CurrentSessionTransaction,
    run_id: Annotated[int, Path(gt=0, description='Agent 运行 ID')],
) -> ResponseSchemaModel[StartShenlunGradingResult]:
    result = await shenlun_grading_service.retry(db=db, run_id=run_id, user_id=request.user.id)
    return response_base.success(data=result)


@router.post('/runs/{run_id}/feedback', summary='纠正申论批改采分点')
async def apply_shenlun_feedback(
    request: Request,
    db: CurrentSessionTransaction,
    run_id: Annotated[int, Path(gt=0, description='Agent 运行 ID')],
    obj: GradingFeedbackParam,
) -> ResponseSchemaModel[GradingRunRead]:
    result = await shenlun_grading_service.apply_feedback(
        db=db,
        run_id=run_id,
        user_id=request.user.id,
        params=obj,
    )
    return response_base.success(data=result)


@router.get('/runs/{run_id}/stream', summary='订阅申论批改 Agent 进度')
async def stream_shenlun_grading(
    request: Request,
    db: CurrentSession,
    run_id: Annotated[int, Path(gt=0, description='Agent 运行 ID')],
) -> StreamingResponse:
    detail = await shenlun_grading_service.get_detail(db=db, run_id=run_id, user_id=request.user.id)

    async def event_stream() -> AsyncIterator[str]:
        initial = {
            'run_id': detail.id,
            'status': detail.status,
            'stage': detail.stage,
            'progress': detail.progress,
            'result': detail.result_payload if detail.status in {'succeeded', 'failed', 'cancelled'} else None,
            'error_message': detail.error_message,
        }
        yield f'data: {json.dumps(initial, ensure_ascii=False, default=str)}\n\n'
        if detail.status in {'succeeded', 'failed', 'cancelled'}:
            return
        async for event in shenlun_grading_service.stream(run_id):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'},
    )
