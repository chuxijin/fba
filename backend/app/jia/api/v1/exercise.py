#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.jia.schema.exercise import (
    CreateExerciseParam,
    GetExerciseListResponse,
    UpdateExerciseParam,
)
from backend.app.jia.service.exercise_service import exercise_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '',
    summary='获取动作列表',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_exercise_list(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='动作名称/搜索关键词')] = None,
    semantic: Annotated[bool, Query(description='是否启用语义搜索（启用时忽略分页）')] = False,
    limit: Annotated[int, Query(description='语义搜索返回数量', ge=1, le=100)] = 20,
) -> ResponseSchemaModel[PageData[GetExerciseListResponse] | list[GetExerciseListResponse]]:
    data = await exercise_service.get_list(db=db, name=name, semantic=semantic, limit=limit)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取动作详情', dependencies=[DependsJwtAuth])
async def get_exercise(
    pk: int,
    db: CurrentSession,
) -> ResponseSchemaModel[GetExerciseListResponse]:
    data = await exercise_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.post('', summary='创建动作', dependencies=[DependsJwtAuth])
async def create_exercise(
    obj: CreateExerciseParam,
    request: Request,
    db: CurrentSessionTransaction,
) -> ResponseSchemaModel[GetExerciseListResponse]:
    data = await exercise_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put('/{pk}', summary='更新动作', dependencies=[DependsJwtAuth])
async def update_exercise(
    pk: int,
    obj: UpdateExerciseParam,
    request: Request,
    db: CurrentSessionTransaction,
) -> ResponseSchemaModel[GetExerciseListResponse]:
    count = await exercise_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        data = await exercise_service.get(db=db, pk=pk)
        return response_base.success(data=data)
    return response_base.fail()


@router.delete('/{pk}', summary='删除动作', dependencies=[DependsJwtAuth])
async def delete_exercise(
    pk: int,
    db: CurrentSessionTransaction,
) -> ResponseModel:
    count = await exercise_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
