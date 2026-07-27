from typing import Annotated

from fastapi import APIRouter, Path, Request

from backend.app.question_bank_v2.schema.practice import (
    CreatePracticeSessionParam,
    GetPracticeResponseDetail,
    GetPracticeSessionDetail,
    GetPracticeSolutionDetail,
    SavePracticeResponseParam,
    SubmitPracticeItemParam,
    SubmitPracticeItemResult,
    SubmitPracticeSessionResult,
)
from backend.app.question_bank_v2.service.practice_service import practice_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth])


@router.post('', summary='创建练习会话', name='qbank_v2_create_practice_session')
async def create_practice_session(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreatePracticeSessionParam,
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """按稳定题库 ID 校验刷题权限并固定当前发布版本"""
    data = await practice_service.create(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get('/{session_key}', summary='获取练习会话', name='qbank_v2_get_practice_session')
async def get_practice_session(
    request: Request,
    db: CurrentSession,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """仅会话所有者可以读取投递题目，响应不包含标准答案与解析"""
    data = await practice_service.get(db=db, session_key=session_key, user_id=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/{session_key}/items/{session_item_id}/response',
    summary='自动保存题目答案',
    name='qbank_v2_save_practice_response',
)
async def save_practice_response(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
    session_item_id: Annotated[int, Path(gt=0, description='会话题目 ID')],
    obj: SavePracticeResponseParam,
) -> ResponseSchemaModel[GetPracticeResponseDetail]:
    """按客户端 save_version 乐观锁保存答案草稿"""
    data = await practice_service.save_response(
        db=db,
        session_key=session_key,
        user_id=request.user.id,
        session_item_id=session_item_id,
        obj=obj,
    )
    return response_base.success(data=data)


@router.post(
    '/{session_key}/items/{session_item_id}/submit',
    summary='提交单题答案',
    name='qbank_v2_submit_practice_item',
)
async def submit_practice_item(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
    session_item_id: Annotated[int, Path(gt=0, description='会话题目 ID')],
    obj: SubmitPracticeItemParam,
) -> ResponseSchemaModel[SubmitPracticeItemResult]:
    """追加不可变作答事实并同步当前判分缓存"""
    data = await practice_service.submit_item(
        db=db,
        session_key=session_key,
        user_id=request.user.id,
        session_item_id=session_item_id,
        obj=obj,
    )
    return response_base.success(data=data)


@router.get(
    '/{session_key}/items/{session_item_id}/solution',
    summary='获取单题答案解析',
    name='qbank_v2_get_practice_solution',
)
async def get_practice_solution(
    request: Request,
    db: CurrentSession,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
    session_item_id: Annotated[int, Path(gt=0, description='会话题目 ID')],
) -> ResponseSchemaModel[GetPracticeSolutionDetail]:
    """练习题提交后可查看；考试和模考必须整卷交卷后查看"""
    data = await practice_service.get_solution(
        db=db,
        session_key=session_key,
        user_id=request.user.id,
        session_item_id=session_item_id,
    )
    return response_base.success(data=data)


@router.post(
    '/{session_key}/submit',
    summary='提交练习会话',
    name='qbank_v2_submit_practice_session',
)
async def submit_practice_session(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
) -> ResponseSchemaModel[SubmitPracticeSessionResult]:
    """交卷后冻结继续作答入口，并保留已有客观题判分结果"""
    data = await practice_service.submit_session(
        db=db,
        session_key=session_key,
        user_id=request.user.id,
    )
    return response_base.success(data=data)
