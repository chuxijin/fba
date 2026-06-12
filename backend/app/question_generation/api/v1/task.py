#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.question_generation.schema import (
    DeleteTaskParam,
    GenerationTaskDetail,
    GenerationTaskListItem,
    StartGenerationParam,
    StartGenerationResult,
)
from backend.app.question_generation.service import question_generation_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '',
    summary='获取出题任务列表',
    dependencies=[Depends(RequestPermission('question_generation:task:read')), DependsRBAC],
)
async def get_task_list(
    db: CurrentSession,
    material_id: Annotated[int | None, Query(description='素材 ID')] = None,
    status: Annotated[str | None, Query(description='任务状态')] = None,
) -> ResponseSchemaModel[list[GenerationTaskListItem]]:
    """
    获取出题任务列表

    :param db: 数据库会话
    :param material_id: 素材 ID
    :param status: 任务状态
    :return:
    """
    data = await question_generation_service.get_task_list(
        db=db,
        material_id=material_id,
        status=status,
    )
    return response_base.success(data=data)


@router.delete(
    '',
    summary='删除出题任务',
    dependencies=[Depends(RequestPermission('question_generation:task:delete')), DependsRBAC],
)
async def delete_task(
    db: CurrentSessionTransaction,
    obj: DeleteTaskParam,
) -> ResponseModel:
    """
    删除出题任务

    :param db: 数据库会话
    :param obj: 删除参数
    :return:
    """
    count = await question_generation_service.delete_task(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.get(
    '/{pk}',
    summary='获取出题任务详情',
    dependencies=[Depends(RequestPermission('question_generation:task:read')), DependsRBAC],
)
async def get_task(
    db: CurrentSession,
    pk: Annotated[int, Path(description='任务 ID')],
) -> ResponseSchemaModel[GenerationTaskDetail]:
    """
    获取出题任务详情

    :param db: 数据库会话
    :param pk: 任务 ID
    :return:
    """
    data = await question_generation_service.get_task(db=db, pk=pk)
    return response_base.success(data=data)


@router.post(
    '/start',
    summary='启动出题任务',
    dependencies=[Depends(RequestPermission('question_generation:task:start')), DependsRBAC],
)
async def start_generation(
    request: Request,
    db: CurrentSessionTransaction,
    obj: StartGenerationParam,
) -> ResponseSchemaModel[StartGenerationResult]:
    """
    启动出题任务

    :param request: 请求对象
    :param db: 数据库会话
    :param obj: 启动参数
    :return:
    """
    data = await question_generation_service.start_generation(
        db=db,
        params=obj,
        created_by=request.user.id,
    )
    return response_base.success(data=data)
