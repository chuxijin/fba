#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, Path, Request

from backend.app.study_plan.crud import study_plan_dao, study_plan_item_dao
from backend.app.study_plan.schema.item import (
    CompleteStudyPlanItemParam,
    GetStudyPlanItemDetail,
    StartStudyPlanItemResult,
)
from backend.app.study_plan.schema.plan import GetStudyPlanDetail
from backend.app.study_plan.schema.record import GetStudyPlanRecordDetail
from backend.app.study_plan.schema.today import TodayStudyPlanDetail
from backend.app.study_plan.service.student_service import (
    complete_item,
    get_item_for_user,
    start_item,
)
from backend.app.study_plan.service.today_service import (
    count_uncompleted_history,
    get_today_plan,
)
from backend.app.study_plan.utils.permission import DependsStudyPlanWhitelist
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(
    dependencies=[DependsJwtAuth, Depends(DependsStudyPlanWhitelist)],
)


@router.get('/today', summary='获取今日计划', response_model=ResponseSchemaModel[TodayStudyPlanDetail])
async def study_plan_get_today(request: Request, db: CurrentSession) -> ResponseSchemaModel[TodayStudyPlanDetail]:
    detail = await get_today_plan(db, request.user.id)
    return response_base.success(data=detail)


@router.get(
    '/items/{item_id}',
    summary='获取计划项详情',
    response_model=ResponseSchemaModel[GetStudyPlanItemDetail],
)
async def study_plan_get_item(
    request: Request,
    db: CurrentSession,
    item_id: int = Path(description='计划项 ID'),
) -> ResponseSchemaModel[GetStudyPlanItemDetail]:
    item = await get_item_for_user(db, item_id, request.user.id)
    return response_base.success(data=GetStudyPlanItemDetail.model_validate(item))


@router.post(
    '/items/{item_id}/start',
    summary='启动计划项',
    response_model=ResponseSchemaModel[StartStudyPlanItemResult],
)
async def study_plan_start(
    request: Request,
    db: CurrentSessionTransaction,
    item_id: int = Path(description='计划项 ID'),
) -> ResponseSchemaModel[StartStudyPlanItemResult]:
    result = await start_item(db, item_id, request.user.id)
    return response_base.success(data=result)


@router.post(
    '/items/{item_id}/complete',
    summary='提交计划项完成',
    response_model=ResponseSchemaModel[GetStudyPlanRecordDetail],
)
async def study_plan_complete(
    request: Request,
    db: CurrentSessionTransaction,
    param: CompleteStudyPlanItemParam,
    item_id: int = Path(description='计划项 ID'),
) -> ResponseSchemaModel[GetStudyPlanRecordDetail]:
    record = await complete_item(db, item_id, request.user.id, param)
    return response_base.success(data=GetStudyPlanRecordDetail.model_validate(record))


@router.get('/me/plans', summary='我的计划列表', response_model=ResponseSchemaModel[list[GetStudyPlanDetail]])
async def study_plan_list_my_plans(
    request: Request, db: CurrentSession,
) -> ResponseSchemaModel[list[GetStudyPlanDetail]]:
    plans = await study_plan_dao.list_by_user(db, request.user.id)
    return response_base.success(
        data=[GetStudyPlanDetail.model_validate(p) for p in plans],
    )


@router.get('/me/uncompleted-count', summary='历史未完成项数量（提醒铃铛）', response_model=ResponseSchemaModel[int])
async def study_plan_my_uncompleted_count(
    request: Request, db: CurrentSession,
) -> ResponseSchemaModel[int]:
    count = await count_uncompleted_history(db, request.user.id)
    return response_base.success(data=count)
