#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.gongkao.schema.practice_log import (
    CreatePracticeLogParam,
    GetPracticeLogDetail,
    ImportPracticeReportParam,
    ImportPracticeReportResult,
    UpdatePracticeLogParam,
)
from backend.app.gongkao.schema.practice_log_vision import (
    ImportPracticeLogVisionParam,
    ImportPracticeLogVisionResult,
)
from backend.app.gongkao.service.practice_log_service import practice_log_service
from backend.app.gongkao.service.practice_log_vision_service import practice_log_vision_service
from backend.app.question_bank_v2.schema.external_practice import GetImportedPracticeDetail
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
)
async def import_practice_log_vision(
    request: Request,
    db: CurrentSession,
    obj: ImportPracticeLogVisionParam,
) -> ResponseSchemaModel[ImportPracticeLogVisionResult]:
    data = await practice_log_vision_service.import_from_vision(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.post('/import-report', summary='导入外部练习报告')
async def import_practice_report(
    request: Request, db: CurrentSessionTransaction, obj: ImportPracticeReportParam
) -> ResponseSchemaModel[ImportPracticeReportResult]:
    data = await practice_log_service.import_report(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get('/comparisons', summary='按科目、模块及直属子模块对比练习')
async def get_practice_comparisons(
    request: Request,
    db: CurrentSession,
    start_date: Annotated[date | None, Query(description='开始日期')] = None,
    end_date: Annotated[date | None, Query(description='结束日期')] = None,
    source_platform: Annotated[str | None, Query(pattern='^(manual|ai|fenbi)$')] = None,
) -> ResponseSchemaModel:
    data = await practice_log_service.get_comparisons(
        db=db, user_id=request.user.id, start_date=start_date, end_date=end_date, source_platform=source_platform
    )
    return response_base.success(data=data)


@router.get(
    '/{pk:int}',
    summary='获取练习记录详情',
)
async def get_practice_log(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='练习记录 ID')],
) -> ResponseSchemaModel[GetPracticeLogDetail]:
    data = await practice_log_service.get(db=db, user_id=request.user.id, pk=pk)
    return response_base.success(data=data)


@router.get('/{pk:int}/questions', summary='获取导入练习的逐题内容、历史作答与完整度')
async def get_practice_log_questions(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='练习记录 ID')],
) -> ResponseSchemaModel[GetImportedPracticeDetail]:
    data = await practice_log_service.get_question_details(db=db, user_id=request.user.id, pk=pk)
    return response_base.success(data=data)


@router.put(
    '/{pk:int}',
    summary='更新练习记录',
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
    '/{pk:int}',
    summary='删除练习记录',
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
