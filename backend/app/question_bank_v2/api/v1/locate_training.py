from typing import Annotated

from fastapi import APIRouter, Path, Request

from backend.app.question_bank_v2.schema.locate_training import (
    CreateLocateTrainingParam,
    GetLocateClickResult,
    GetLocateTrainingResult,
    GetLocateTrainingSessionDetail,
    SubmitLocateClickParam,
    SubmitLocateCompletionParam,
)
from backend.app.question_bank_v2.service.locate_training_service import locate_training_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth])


@router.post('/sessions', summary='创建找数训练会话')
async def create_locate_training_session(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateLocateTrainingParam,
) -> ResponseSchemaModel[GetLocateTrainingSessionDetail]:
    """按题量随机组卷，投递不含答案的找数训练题目"""
    data = await locate_training_service.create(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get('/sessions/{session_key}', summary='获取找数训练会话')
async def get_locate_training_session(
    request: Request,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
) -> ResponseSchemaModel[GetLocateTrainingSessionDetail]:
    """恢复进行中的找数训练会话"""
    data = await locate_training_service.get(session_key=session_key, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('/sessions/{session_key}/clicks', summary='判定单次找数点击')
async def submit_locate_click(
    request: Request,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
    obj: SubmitLocateClickParam,
) -> ResponseSchemaModel[GetLocateClickResult]:
    """命中目标锚点累计进度，错误点击即时提示不计入进度"""
    data = await locate_training_service.judge(session_key=session_key, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.post('/sessions/{session_key}/completion', summary='完成找数训练并结算')
async def complete_locate_training(
    request: Request,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
    obj: SubmitLocateCompletionParam | None = None,
) -> ResponseSchemaModel[GetLocateTrainingResult]:
    """返回点击命中率、无错题数和训练用时，支持携带逐题偷看/放弃行为数据，会话随之销毁"""
    data = await locate_training_service.complete(
        session_key=session_key,
        user_id=request.user.id,
        question_meta=obj.question_meta if obj is not None else None,
    )
    return response_base.success(data=data)
