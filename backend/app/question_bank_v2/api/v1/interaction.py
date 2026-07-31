from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.question_bank_v2.schema.material import (
    CreateQuestionInteractionParam,
    GetQuestionInteractionDetail,
    UpdateQuestionInteractionParam,
)
from backend.app.question_bank_v2.service.interaction_service import interaction_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:update')), DependsRBAC])


@router.get(
    '/interactions',
    summary='获取题目交互定义列表',
    name='qbank_v2_list_question_interactions',
)
async def list_question_interactions(
    db: CurrentSession,
    question_id: Annotated[int, Query(gt=0, description='题目稳定身份 ID')],
) -> ResponseSchemaModel[list[GetQuestionInteractionDetail]]:
    data = await interaction_service.get_all(db=db, question_id=question_id)
    return response_base.success(data=data)


@router.get(
    '/{question_id}/revisions/{revision_id}/interactions',
    summary='获取题目版本交互定义',
    name='qbank_v2_get_question_interactions',
)
async def get_question_interactions(
    db: CurrentSession,
    question_id: Annotated[int, Path(gt=0, description='题目稳定身份 ID')],
    revision_id: Annotated[int, Path(gt=0, description='题目版本 ID')],
) -> ResponseSchemaModel[list[GetQuestionInteractionDetail]]:
    data = await interaction_service.get_all(db=db, question_id=question_id)
    return response_base.success(data=data)


@router.post(
    '/{question_id}/interactions',
    summary='创建题目交互定义',
    name='qbank_v2_create_question_interaction_simple',
)
async def create_question_interaction_simple(
    request: Request,
    db: CurrentSessionTransaction,
    question_id: Annotated[int, Path(gt=0, description='题目稳定身份 ID')],
    obj: CreateQuestionInteractionParam,
) -> ResponseSchemaModel[GetQuestionInteractionDetail]:
    data = await interaction_service.create(
        db=db,
        question_id=question_id,
        obj=obj,
        user_id=request.user.id,
    )
    return response_base.success(data=data)


@router.put(
    '/{question_id}/interactions/{interaction_id}',
    summary='更新题目交互定义',
    name='qbank_v2_update_question_interaction_simple',
)
async def update_question_interaction_simple(
    request: Request,
    db: CurrentSessionTransaction,
    question_id: Annotated[int, Path(gt=0, description='题目稳定身份 ID')],
    interaction_id: Annotated[int, Path(gt=0, description='交互定义 ID')],
    obj: UpdateQuestionInteractionParam,
) -> ResponseSchemaModel[GetQuestionInteractionDetail]:
    data = await interaction_service.update(
        db=db,
        question_id=question_id,
        interaction_id=interaction_id,
        obj=obj,
        user_id=request.user.id,
    )
    return response_base.success(data=data)


@router.delete(
    '/{question_id}/interactions/{interaction_id}',
    summary='删除题目交互定义',
    name='qbank_v2_delete_question_interaction_simple',
)
async def delete_question_interaction_simple(
    db: CurrentSessionTransaction,
    question_id: Annotated[int, Path(gt=0, description='题目稳定身份 ID')],
    interaction_id: Annotated[int, Path(gt=0, description='交互定义 ID')],
) -> ResponseSchemaModel[None]:
    await interaction_service.delete(
        db=db,
        question_id=question_id,
        interaction_id=interaction_id,
    )
    return response_base.success()
