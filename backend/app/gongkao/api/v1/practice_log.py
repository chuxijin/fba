#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.gongkao.schema.practice_log import (
    CreatePracticeLogParam,
    GetPracticeLogDetail,
    UpdatePracticeLogParam,
)
from backend.app.gongkao.schema.practice_log_vision import (
    ImportPracticeLogVisionParam,
    ImportPracticeLogVisionResult,
)
from backend.app.gongkao.service.practice_log_service import practice_log_service
from backend.app.gongkao.service.practice_log_vision_service import practice_log_vision_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth])


@router.get(
    '',
    summary='获取练习记录列表',
    response_model=ResponseSchemaModel[PageData[GetPracticeLogDetail]],
    dependencies=[DependsPagination],
)
async def get_practice_log_list(
    request: Request,
    db: CurrentSession,
    material_type: Annotated[str | None, Query(description='材料类型（exam/practice/special）')] = None,
    material_title: Annotated[str | None, Query(description='材料标题关键词')] = None,
    start_date: Annotated[date | None, Query(description='开始日期')] = None,
    end_date: Annotated[date | None, Query(description='结束日期')] = None,
) -> ResponseModel:
    data = await practice_log_service.get_list(
        db=db,
        user_id=request.user.id,
        material_type=material_type,
        material_title=material_title,
        start_date=start_date,
        end_date=end_date,
    )
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建练习记录',
    response_model=ResponseSchemaModel[GetPracticeLogDetail],
)
async def create_practice_log(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreatePracticeLogParam,
) -> ResponseSchemaModel[GetPracticeLogDetail]:
    data = await practice_log_service.create(db=db, user_id=request.user.id, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.get(
    '/trends',
    summary='获取练习趋势',
    response_model=ResponseSchemaModel,
)
async def get_practice_log_trends(
    request: Request,
    db: CurrentSession,
    days: Annotated[int | None, Query(description='最近 N 天')] = None,
) -> ResponseSchemaModel:
    data = await practice_log_service.get_trends(db=db, user_id=request.user.id, limit_days=days)
    return response_base.success(data=data)


@router.post(
    '/import-vision',
    summary='AI 智能导入练习记录',
    response_model=ResponseSchemaModel[ImportPracticeLogVisionResult],
)
async def import_practice_log_vision(
    request: Request,
    db: CurrentSession,
    obj: ImportPracticeLogVisionParam,
) -> ResponseSchemaModel[ImportPracticeLogVisionResult]:
    data = await practice_log_vision_service.import_from_vision(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get(
    '/{pk}',
    summary='获取练习记录详情',
    response_model=ResponseSchemaModel[GetPracticeLogDetail],
)
async def get_practice_log(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='练习记录 ID')],
) -> ResponseSchemaModel[GetPracticeLogDetail]:
    data = await practice_log_service.get(db=db, user_id=request.user.id, pk=pk)
    return response_base.success(data=data)


@router.put(
    '/{pk}',
    summary='更新练习记录',
    response_model=ResponseSchemaModel[GetPracticeLogDetail],
)
async def update_practice_log(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='练习记录 ID')],
    obj: UpdatePracticeLogParam,
) -> ResponseSchemaModel[GetPracticeLogDetail]:
    data = await practice_log_service.update(db=db, user_id=request.user.id, pk=pk, obj=obj)
    return response_base.success(data=data)


@router.delete(
    '/{pk}',
    summary='删除练习记录',
    response_model=ResponseModel,
)
async def delete_practice_log(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='练习记录 ID')],
) -> ResponseModel:
    count = await practice_log_service.delete(db=db, user_id=request.user.id, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
