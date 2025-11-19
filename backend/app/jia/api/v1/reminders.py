#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.jia.schema.reminders import CreateReminderParam, DeleteReminderParam, GetReminderDetail, UpdateReminderParam
from backend.app.jia.service.reminders_service import reminder_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取提醒详情', dependencies=[DependsJwtAuth])
async def get_jia_reminder(
    db: CurrentSession, pk: Annotated[int, Path(description='提醒 ID')]
) -> ResponseSchemaModel[GetReminderDetail]:
    data = await reminder_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取提醒列表', dependencies=[DependsJwtAuth])
async def get_jia_reminder_list(
    db: CurrentSession,
    scheduled_time_start: Annotated[int | None, Query(description='开始计划时间')] = None,
    scheduled_time_end: Annotated[int | None, Query(description='结束计划时间')] = None,
    is_completed: Annotated[int | None, Query(description='是否完成')] = None,
    is_important: Annotated[int | None, Query(description='是否重要')] = None,
    is_starred: Annotated[int | None, Query(description='是否星标')] = None,
    is_pinned: Annotated[int | None, Query(description='是否置顶')] = None,
    priority: Annotated[int | None, Query(description='优先级')] = None,
    sync_status: Annotated[str | None, Query(description='同步状态')] = None,
) -> ResponseSchemaModel[list[GetReminderDetail]]:
    data = await reminder_service.get_list(
        db=db,
        scheduled_time_start=scheduled_time_start,
        scheduled_time_end=scheduled_time_end,
        is_completed=is_completed,
        is_important=is_important,
        is_starred=is_starred,
        is_pinned=is_pinned,
        priority=priority,
        sync_status=sync_status,
    )
    return response_base.success(data=data)


@router.get('/all', summary='获取所有提醒', dependencies=[DependsJwtAuth])
async def get_all_jia_reminders(db: CurrentSession, request: Request) -> ResponseSchemaModel[list[GetReminderDetail]]:
    data = await reminder_service.get_all(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('', summary='创建提醒', dependencies=[DependsJwtAuth])
async def create_jia_reminder(
    db: CurrentSessionTransaction, request: Request, obj: CreateReminderParam
) -> ResponseModel:
    await reminder_service.create(db=db, obj=obj, user_id=request.user.id)
    return response_base.success()


@router.put('/{pk}', summary='更新提醒', dependencies=[DependsJwtAuth])
async def update_jia_reminder(
    db: CurrentSessionTransaction,
    request: Request,
    pk: Annotated[int, Path(description='提醒 ID')],
    obj: UpdateReminderParam,
) -> ResponseModel:
    count = await reminder_service.update(db=db, pk=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('', summary='批量删除提醒', dependencies=[DependsJwtAuth])
async def delete_jia_reminder(db: CurrentSessionTransaction, obj: DeleteReminderParam) -> ResponseModel:
    count = await reminder_service.delete(db=db, pks=obj.pks)
    if count > 0:
        return response_base.success()
    return response_base.fail()

