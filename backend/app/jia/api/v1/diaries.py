#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.jia.schema.diaries import CreateDiaryParam, DeleteDiaryParam, GetDiaryDetail, UpdateDiaryParam
from backend.app.jia.service.diaries_service import diary_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取日记详情', dependencies=[DependsJwtAuth])
async def get_jia_diary(
    db: CurrentSession, pk: Annotated[int, Path(description='日记 ID')]
) -> ResponseSchemaModel[GetDiaryDetail]:
    data = await diary_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('/date/{date}', summary='通过日期获取日记', dependencies=[DependsJwtAuth])
async def get_jia_diary_by_date(
    db: CurrentSession, request: Request, date: Annotated[int, Path(description='日期时间戳')]
) -> ResponseSchemaModel[GetDiaryDetail | None]:
    data = await diary_service.get_by_date(db=db, date=date, user_id=request.user.id)
    return response_base.success(data=data)


@router.get('', summary='获取日记列表', dependencies=[DependsJwtAuth])
async def get_jia_diary_list(
    db: CurrentSession,
    date_start: Annotated[int | None, Query(description='开始日期时间戳')] = None,
    date_end: Annotated[int | None, Query(description='结束日期时间戳')] = None,
    mood: Annotated[str | None, Query(description='主要心情')] = None,
    weather: Annotated[str | None, Query(description='天气')] = None,
    is_starred: Annotated[int | None, Query(description='是否星标')] = None,
    is_pinned: Annotated[int | None, Query(description='是否置顶')] = None,
    priority: Annotated[int | None, Query(description='优先级')] = None,
    sync_status: Annotated[str | None, Query(description='同步状态')] = None,
) -> ResponseSchemaModel[list[GetDiaryDetail]]:
    data = await diary_service.get_list(
        db=db,
        date_start=date_start,
        date_end=date_end,
        mood=mood,
        weather=weather,
        is_starred=is_starred,
        is_pinned=is_pinned,
        priority=priority,
        sync_status=sync_status,
    )
    return response_base.success(data=data)


@router.get('/all', summary='获取所有日记', dependencies=[DependsJwtAuth])
async def get_all_jia_diaries(db: CurrentSession, request: Request) -> ResponseSchemaModel[list[GetDiaryDetail]]:
    data = await diary_service.get_all(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('', summary='创建日记', dependencies=[DependsJwtAuth])
async def create_jia_diary(
    db: CurrentSessionTransaction, request: Request, obj: CreateDiaryParam
) -> ResponseModel:
    await diary_service.create(db=db, obj=obj, user_id=request.user.id)
    return response_base.success()


@router.put('/{pk}', summary='更新日记', dependencies=[DependsJwtAuth])
async def update_jia_diary(
    db: CurrentSessionTransaction,
    request: Request,
    pk: Annotated[int, Path(description='日记 ID')],
    obj: UpdateDiaryParam,
) -> ResponseModel:
    count = await diary_service.update(db=db, pk=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('', summary='批量删除日记', dependencies=[DependsJwtAuth])
async def delete_jia_diary(db: CurrentSessionTransaction, obj: DeleteDiaryParam) -> ResponseModel:
    count = await diary_service.delete(db=db, pks=obj.pks)
    if count > 0:
        return response_base.success()
    return response_base.fail()

