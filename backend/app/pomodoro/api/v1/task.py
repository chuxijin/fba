#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.pomodoro.enums import PomodoroTaskStatus
from backend.app.pomodoro.schema.task import (
    CreatePomodoroTaskParam,
    GeneratePomodoroRepeatTaskParam,
    GetPomodoroTaskDetail,
    GetPomodoroTaskListItem,
    GetPomodoroRepeatTaskGenerateResult,
    UpdatePomodoroTaskParam,
)
from backend.app.pomodoro.service.task_service import pomodoro_task_service
from backend.app.admin.service.tag_service import sys_tag_target_service
from backend.app.admin.service.cat_service import sys_cat_target_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/pomodoro/tasks', tags=['番茄任务'], dependencies=[DependsJwtAuth])


@router.get(
    '',
    summary='获取番茄任务列表',
    name='pomodoro_task_list',
    operation_id='pomodoroTaskList',
    response_model=ResponseSchemaModel[PageData[GetPomodoroTaskListItem]],
    dependencies=[DependsPagination],
)
async def get_pomodoro_task_list(
    request: Request,
    db: CurrentSessionTransaction,
    status: Annotated[PomodoroTaskStatus | None, Query(description='任务状态')] = None,
    keyword: Annotated[str | None, Query(description='标题关键词')] = None,
) -> ResponseModel:
    """
    获取番茄任务列表

    :param request: 请求对象
    :param db: 数据库会话
    :param status: 任务状态
    :param keyword: 标题关键词
    :return:
    """
    data = await pomodoro_task_service.get_list(
        db=db,
        user_id=request.user.id,
        status=status,
        keyword=keyword,
    )
    return response_base.success(data=data)


@router.post(
    '/repeat/generate',
    summary='生成番茄重复任务',
    name='pomodoro_task_generate_repeat',
    response_model=ResponseSchemaModel[GetPomodoroRepeatTaskGenerateResult],
)
async def generate_pomodoro_repeat_tasks(
    request: Request,
    db: CurrentSessionTransaction,
    obj: GeneratePomodoroRepeatTaskParam | None = None,
) -> ResponseSchemaModel[GetPomodoroRepeatTaskGenerateResult]:
    """
    生成番茄重复任务

    :param request: 请求对象
    :param db: 数据库会话
    :param obj: 生成参数
    :return:
    """
    target_date = obj.target_date if obj else None
    data = await pomodoro_task_service.generate_repeat_tasks(
        db=db,
        user_id=request.user.id,
        target_date=target_date,
    )
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建番茄任务',
    name='pomodoro_task_create',
    operation_id='pomodoroTaskCreate',
    response_model=ResponseSchemaModel[GetPomodoroTaskDetail],
)
async def create_pomodoro_task(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreatePomodoroTaskParam,
) -> ResponseSchemaModel[GetPomodoroTaskDetail]:
    """
    创建番茄任务

    :param request: 请求对象
    :param db: 数据库会话
    :param obj: 创建参数
    :return:
    """
    data = await pomodoro_task_service.create(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get(
    '/{task_id}',
    summary='获取番茄任务详情',
    name='pomodoro_task_get',
    operation_id='pomodoroTaskGet',
    response_model=ResponseSchemaModel[GetPomodoroTaskDetail],
)
async def get_pomodoro_task(
    request: Request,
    db: CurrentSession,
    task_id: Annotated[int, Path(description='任务 ID')],
) -> ResponseSchemaModel[GetPomodoroTaskDetail]:
    """
    获取番茄任务详情

    :param request: 请求对象
    :param db: 数据库会话
    :param task_id: 任务 ID
    :return:
    """
    task = await pomodoro_task_service.get(db=db, user_id=request.user.id, task_id=task_id)
    tags = await sys_tag_target_service.get_targets(db=db, target_type='pomodoro_task', target_id=task_id)
    categories = await sys_cat_target_service.get_targets(db=db, target_type='pomodoro_task', target_id=task_id)
    data = {
        **GetPomodoroTaskDetail.model_validate(task).model_dump(),
        'tags': tags,
        'categories': categories,
    }
    return response_base.success(data=data)


@router.put(
    '/{task_id}',
    summary='更新番茄任务',
    name='pomodoro_task_update',
    operation_id='pomodoroTaskUpdate',
    response_model=ResponseSchemaModel[GetPomodoroTaskDetail],
)
async def update_pomodoro_task(
    request: Request,
    db: CurrentSessionTransaction,
    task_id: Annotated[int, Path(description='任务 ID')],
    obj: UpdatePomodoroTaskParam,
) -> ResponseSchemaModel[GetPomodoroTaskDetail]:
    """
    更新番茄任务

    :param request: 请求对象
    :param db: 数据库会话
    :param task_id: 任务 ID
    :param obj: 更新参数
    :return:
    """
    data = await pomodoro_task_service.update(db=db, user_id=request.user.id, task_id=task_id, obj=obj)
    return response_base.success(data=data)


@router.patch(
    '/{task_id}/complete',
    summary='完成番茄任务',
    name='pomodoro_task_complete',
    operation_id='pomodoroTaskComplete',
    response_model=ResponseSchemaModel[GetPomodoroTaskDetail],
)
async def complete_pomodoro_task(
    request: Request,
    db: CurrentSessionTransaction,
    task_id: Annotated[int, Path(description='任务 ID')],
) -> ResponseSchemaModel[GetPomodoroTaskDetail]:
    """
    完成番茄任务

    :param request: 请求对象
    :param db: 数据库会话
    :param task_id: 任务 ID
    :return:
    """
    data = await pomodoro_task_service.complete(db=db, user_id=request.user.id, task_id=task_id)
    return response_base.success(data=data)


@router.delete(
    '/{task_id}',
    summary='删除番茄任务',
    name='pomodoro_task_delete',
    operation_id='pomodoroTaskDelete',
)
async def delete_pomodoro_task(
    request: Request,
    db: CurrentSessionTransaction,
    task_id: Annotated[int, Path(description='任务 ID')],
) -> ResponseModel:
    """
    删除番茄任务

    :param request: 请求对象
    :param db: 数据库会话
    :param task_id: 任务 ID
    :return:
    """
    await pomodoro_task_service.delete(db=db, user_id=request.user.id, task_id=task_id)
    return response_base.success()
