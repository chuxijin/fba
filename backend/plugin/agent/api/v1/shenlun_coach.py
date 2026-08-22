import json

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Path, Request
from starlette.responses import StreamingResponse

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.agent.schema.coach import (
    CoachAnalyticsRead,
    CoachMemoryRead,
    CoachMessageParam,
    CoachRecommendationRead,
    CoachRunRead,
    CoachSessionListRead,
    CoachSessionRead,
    CreateCoachSessionParam,
    GenerateTrainingPlanParam,
    StartCoachRunResult,
    TrainingPlanListRead,
    TrainingPlanRead,
)
from backend.plugin.agent.service.coach_service import shenlun_coach_service

router = APIRouter(dependencies=[DependsJwtAuth])


@router.post('/sessions', summary='创建申论教练会话')
async def create_coach_session(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateCoachSessionParam,
) -> ResponseSchemaModel[CoachSessionRead]:
    result = await shenlun_coach_service.create_session(
        db=db,
        user_id=request.user.id,
        title=obj.title,
        grading_run_id=obj.grading_run_id,
    )
    return response_base.success(data=result)


@router.get('/sessions', summary='获取申论教练会话列表')
async def list_coach_sessions(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[CoachSessionListRead]]:
    result = await shenlun_coach_service.list_sessions(db=db, user_id=request.user.id)
    return response_base.success(data=result)


@router.get('/sessions/{session_id}', summary='获取申论教练会话')
async def get_coach_session(
    request: Request,
    db: CurrentSession,
    session_id: Annotated[int, Path(gt=0, description='教练会话 ID')],
) -> ResponseSchemaModel[CoachSessionRead]:
    result = await shenlun_coach_service.get_session(db=db, session_id=session_id, user_id=request.user.id)
    return response_base.success(data=result)


@router.post('/sessions/{session_id}/archive', summary='归档申论教练会话')
async def archive_coach_session(
    request: Request,
    db: CurrentSessionTransaction,
    session_id: Annotated[int, Path(gt=0, description='教练会话 ID')],
) -> ResponseSchemaModel[CoachSessionRead]:
    result = await shenlun_coach_service.archive_session(db=db, session_id=session_id, user_id=request.user.id)
    return response_base.success(data=result)


@router.post('/sessions/{session_id}/messages', summary='发送申论教练消息')
async def send_coach_message(
    request: Request,
    db: CurrentSessionTransaction,
    session_id: Annotated[int, Path(gt=0, description='教练会话 ID')],
    obj: CoachMessageParam,
) -> ResponseSchemaModel[CoachSessionRead]:
    result = await shenlun_coach_service.send_message(
        db=db,
        session_id=session_id,
        user_id=request.user.id,
        params=obj,
    )
    return response_base.success(data=result)


@router.post('/sessions/{session_id}/message-runs', summary='异步发送申论教练消息')
async def start_coach_message_run(
    request: Request,
    db: CurrentSessionTransaction,
    session_id: Annotated[int, Path(gt=0, description='教练会话 ID')],
    obj: CoachMessageParam,
) -> ResponseSchemaModel[StartCoachRunResult]:
    result = await shenlun_coach_service.start_message_run(
        db=db,
        session_id=session_id,
        user_id=request.user.id,
        params=obj,
    )
    return response_base.success(data=result)


@router.get('/runs/{run_id}', summary='获取申论教练运行结果')
async def get_coach_run(
    request: Request,
    db: CurrentSession,
    run_id: Annotated[int, Path(gt=0, description='教练运行 ID')],
) -> ResponseSchemaModel[CoachRunRead]:
    result = await shenlun_coach_service.get_run(db=db, run_id=run_id, user_id=request.user.id)
    return response_base.success(data=result)


@router.get('/runs/{run_id}/stream', summary='订阅申论教练运行进度')
async def stream_coach_run(
    request: Request,
    db: CurrentSession,
    run_id: Annotated[int, Path(gt=0, description='教练运行 ID')],
) -> StreamingResponse:
    detail = await shenlun_coach_service.get_run(db=db, run_id=run_id, user_id=request.user.id)

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
        async for event in shenlun_coach_service.stream(run_id):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'},
    )


@router.get('/memories', summary='获取申论教练长期记忆')
async def get_coach_memories(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[CoachMemoryRead]]:
    memories = await shenlun_coach_service.list_memories(db=db, user_id=request.user.id)
    return response_base.success(data=memories)


@router.get('/recommendations', summary='获取申论下一题推荐')
async def get_coach_recommendations(
    request: Request,
    db: CurrentSession,
    module: str = 'overview',
) -> ResponseSchemaModel[list[CoachRecommendationRead]]:
    from backend.plugin.agent.service.coach_recommendation import coach_recommendation_service

    rows = await coach_recommendation_service.recommend(
        db=db,
        user_id=request.user.id,
        module=module,
        limit=5,
    )
    return response_base.success(data=[CoachRecommendationRead(**row) for row in rows])


@router.post('/plans', summary='生成申论训练计划')
async def generate_training_plan(
    request: Request,
    db: CurrentSessionTransaction,
    obj: GenerateTrainingPlanParam,
) -> ResponseSchemaModel[TrainingPlanRead]:
    result = await shenlun_coach_service.generate_plan(db=db, user_id=request.user.id, params=obj)
    return response_base.success(data=result)


@router.get('/plans', summary='获取申论训练计划列表')
async def list_training_plans(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[TrainingPlanListRead]]:
    result = await shenlun_coach_service.list_plans(db=db, user_id=request.user.id)
    return response_base.success(data=result)


@router.get('/plans/{plan_id}', summary='获取申论训练计划')
async def get_training_plan(
    request: Request,
    db: CurrentSession,
    plan_id: Annotated[int, Path(gt=0, description='训练计划 ID')],
) -> ResponseSchemaModel[TrainingPlanRead]:
    result = await shenlun_coach_service.get_plan(db=db, plan_id=plan_id, user_id=request.user.id)
    return response_base.success(data=result)


@router.post('/plan-items/{item_id}/complete', summary='完成申论训练计划项')
async def complete_training_plan_item(
    request: Request,
    db: CurrentSessionTransaction,
    item_id: Annotated[int, Path(gt=0, description='训练计划项 ID')],
) -> ResponseSchemaModel[TrainingPlanRead]:
    result = await shenlun_coach_service.complete_plan_item(db=db, item_id=item_id, user_id=request.user.id)
    return response_base.success(data=result)


@router.get('/analytics', summary='获取申论训练分析')
async def get_coach_analytics(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[CoachAnalyticsRead]:
    result = await shenlun_coach_service.analytics(db=db, user_id=request.user.id)
    return response_base.success(data=result)
