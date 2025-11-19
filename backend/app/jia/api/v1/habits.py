#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.jia.schema.habits import (
    CreateHabitParam,
    CreateHabitRecordParam,
    DeleteHabitParam,
    DeleteHabitRecordParam,
    GetHabitDetail,
    GetHabitRecordDetail,
    UpdateHabitParam,
    UpdateHabitRecordParam,
)
from backend.app.jia.service.habits_service import habit_record_service, habit_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取习惯详情', dependencies=[DependsJwtAuth])
async def get_jia_habit(
    db: CurrentSession, pk: Annotated[int, Path(description='习惯 ID')]
) -> ResponseSchemaModel[GetHabitDetail]:
    data = await habit_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取习惯列表', dependencies=[DependsJwtAuth])
async def get_jia_habit_list(
    db: CurrentSession,
    difficulty: Annotated[int | None, Query(description='难度等级')] = None,
    target_type: Annotated[str | None, Query(description='目标类型')] = None,
    is_archived: Annotated[int | None, Query(description='是否归档')] = None,
    is_pinned: Annotated[int | None, Query(description='是否置顶')] = None,
    sync_status: Annotated[str | None, Query(description='同步状态')] = None,
) -> ResponseSchemaModel[list[GetHabitDetail]]:
    data = await habit_service.get_list(
        db=db,
        difficulty=difficulty,
        target_type=target_type,
        is_archived=is_archived,
        is_pinned=is_pinned,
        sync_status=sync_status,
    )
    return response_base.success(data=data)


@router.get('/all', summary='获取所有习惯', dependencies=[DependsJwtAuth])
async def get_all_jia_habits(db: CurrentSession, request: Request) -> ResponseSchemaModel[list[GetHabitDetail]]:
    data = await habit_service.get_all(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('', summary='创建习惯', dependencies=[DependsJwtAuth])
async def create_jia_habit(
    db: CurrentSessionTransaction, request: Request, obj: CreateHabitParam
) -> ResponseModel:
    await habit_service.create(db=db, obj=obj, user_id=request.user.id)
    return response_base.success()


@router.put('/{pk}', summary='更新习惯', dependencies=[DependsJwtAuth])
async def update_jia_habit(
    db: CurrentSessionTransaction,
    request: Request,
    pk: Annotated[int, Path(description='习惯 ID')],
    obj: UpdateHabitParam,
) -> ResponseModel:
    count = await habit_service.update(db=db, pk=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('', summary='批量删除习惯', dependencies=[DependsJwtAuth])
async def delete_jia_habit(db: CurrentSessionTransaction, obj: DeleteHabitParam) -> ResponseModel:
    count = await habit_service.delete(db=db, pks=obj.pks)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.get('/{habit_id}/records', summary='获取习惯的所有打卡记录', dependencies=[DependsJwtAuth])
async def get_jia_habit_records(
    db: CurrentSession, habit_id: Annotated[int, Path(description='习惯 ID')]
) -> ResponseSchemaModel[list[GetHabitRecordDetail]]:
    data = await habit_record_service.get_by_habit(db=db, habit_id=habit_id)
    return response_base.success(data=data)


@router.get('/{habit_id}/records/date/{date}', summary='获取指定日期的打卡记录', dependencies=[DependsJwtAuth])
async def get_jia_habit_record_by_date(
    db: CurrentSession,
    habit_id: Annotated[int, Path(description='习惯 ID')],
    date: Annotated[int, Path(description='日期时间戳')],
) -> ResponseSchemaModel[GetHabitRecordDetail | None]:
    data = await habit_record_service.get_by_habit_and_date(db=db, habit_id=habit_id, date=date)
    return response_base.success(data=data)


@router.get('/records/{pk}', summary='获取打卡记录详情', dependencies=[DependsJwtAuth])
async def get_jia_habit_record(
    db: CurrentSession, pk: Annotated[int, Path(description='记录 ID')]
) -> ResponseSchemaModel[GetHabitRecordDetail]:
    data = await habit_record_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('/records', summary='获取打卡记录列表', dependencies=[DependsJwtAuth])
async def get_jia_habit_record_list(
    db: CurrentSession,
    habit_id: Annotated[int | None, Query(description='习惯 ID')] = None,
    date_start: Annotated[int | None, Query(description='开始日期时间戳')] = None,
    date_end: Annotated[int | None, Query(description='结束日期时间戳')] = None,
    status: Annotated[str | None, Query(description='状态')] = None,
    checkin_type: Annotated[str | None, Query(description='打卡类型')] = None,
) -> ResponseSchemaModel[list[GetHabitRecordDetail]]:
    data = await habit_record_service.get_list(
        db=db, habit_id=habit_id, date_start=date_start, date_end=date_end, status=status, checkin_type=checkin_type
    )
    return response_base.success(data=data)


@router.post('/records', summary='创建打卡记录', dependencies=[DependsJwtAuth])
async def create_jia_habit_record(
    db: CurrentSessionTransaction, request: Request, obj: CreateHabitRecordParam
) -> ResponseModel:
    await habit_record_service.create(db=db, obj=obj, user_id=request.user.id)
    return response_base.success()


@router.put('/records/{pk}', summary='更新打卡记录', dependencies=[DependsJwtAuth])
async def update_jia_habit_record(
    db: CurrentSessionTransaction,
    request: Request,
    pk: Annotated[int, Path(description='记录 ID')],
    obj: UpdateHabitRecordParam,
) -> ResponseModel:
    count = await habit_record_service.update(db=db, pk=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/records', summary='批量删除打卡记录', dependencies=[DependsJwtAuth])
async def delete_jia_habit_record(db: CurrentSessionTransaction, obj: DeleteHabitRecordParam) -> ResponseModel:
    count = await habit_record_service.delete(db=db, pks=obj.pks)
    if count > 0:
        return response_base.success()
    return response_base.fail()

