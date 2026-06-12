#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.question_generation.schema import (
    CandidateListItem,
    CandidateReviewParam,
    DeleteCandidateParam,
    GetCandidateDetail,
)
from backend.app.question_generation.service import question_generation_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '',
    summary='获取候选题列表',
    dependencies=[Depends(RequestPermission('question_generation:candidate:read')), DependsRBAC],
)
async def get_candidate_list(
    db: CurrentSession,
    task_id: Annotated[int | None, Query(description='任务 ID')] = None,
    material_id: Annotated[int | None, Query(description='素材 ID')] = None,
    status: Annotated[str | None, Query(description='候选题状态')] = None,
) -> ResponseSchemaModel[list[CandidateListItem]]:
    """
    获取候选题列表

    :param db: 数据库会话
    :param task_id: 任务 ID
    :param material_id: 素材 ID
    :param status: 候选题状态
    :return:
    """
    data = await question_generation_service.get_candidate_list(
        db=db,
        task_id=task_id,
        material_id=material_id,
        status=status,
    )
    return response_base.success(data=data)


@router.get(
    '/{pk}',
    summary='获取候选题详情',
    dependencies=[Depends(RequestPermission('question_generation:candidate:read')), DependsRBAC],
)
async def get_candidate(
    db: CurrentSession,
    pk: Annotated[int, Path(description='候选题 ID')],
) -> ResponseSchemaModel[GetCandidateDetail]:
    """
    获取候选题详情

    :param db: 数据库会话
    :param pk: 候选题 ID
    :return:
    """
    data = await question_generation_service.get_candidate(db=db, pk=pk)
    return response_base.success(data=data)


@router.post(
    '/{pk}/review',
    summary='审核候选题',
    dependencies=[Depends(RequestPermission('question_generation:candidate:review')), DependsRBAC],
)
async def review_candidate(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='候选题 ID')],
    obj: CandidateReviewParam,
) -> ResponseModel:
    """
    审核候选题

    :param request: 请求对象
    :param db: 数据库会话
    :param pk: 候选题 ID
    :param obj: 审核参数
    :return:
    """
    await question_generation_service.review_candidate(
        db=db,
        pk=pk,
        obj=obj,
        updated_by=request.user.id,
    )
    return response_base.success()


@router.delete(
    '',
    summary='删除候选题',
    dependencies=[Depends(RequestPermission('question_generation:candidate:delete')), DependsRBAC],
)
async def delete_candidate(
    db: CurrentSessionTransaction,
    obj: DeleteCandidateParam,
) -> ResponseModel:
    """
    删除候选题

    :param db: 数据库会话
    :param obj: 删除参数
    :return:
    """
    count = await question_generation_service.delete_candidate(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
