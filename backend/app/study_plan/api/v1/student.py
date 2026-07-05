#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

from fastapi import APIRouter, Depends, Path, Query, Request, Response

from backend.app.study_plan.crud import study_plan_dao
from backend.app.study_plan.schema.ability import (
    BatchSubmitStudyAbilityAttemptParam,
    BatchSubmitStudyAbilityAttemptResult,
    GetStudyAbilityAttemptDetail,
    GetStudyAbilityAttemptListItem,
    GetStudyPlanAbilityCatalogItem,
    GetStudyUserCategoryProfileDetail,
    SubmitStudyAbilityAttemptParam,
    SubmitStudyAbilityAttemptResult,
)
from backend.app.study_plan.schema.item import (
    CompleteStudyPlanItemParam,
    GetStudyPlanItemDetail,
    StartStudyPlanItemResult,
)
from backend.app.study_plan.schema.plan import GetStudyPlanDetail, StudyPlanProgress
from backend.app.study_plan.schema.record import GetStudyPlanRecordDetail
from backend.app.study_plan.schema.today import TodayStudyPlanDetail
from backend.app.study_plan.service.ability_catalog import list_ability_catalog_with_db
from backend.app.study_plan.service.ability_profile import (
    batch_submit_ability_attempts,
    get_user_attempt_detail,
    list_user_attempts,
    list_user_category_profiles,
    submit_ability_attempt,
)
from backend.app.study_plan.service.item_detail_service import build_item_detail, build_item_details
from backend.app.study_plan.service.student_service import (
    complete_item,
    get_item_for_user,
    get_plan_progress_for_user,
    list_items_of_my_plan,
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
    dependencies=[DependsJwtAuth],
)
STUDY_PLAN_WHITELIST_DEPENDENCIES = [Depends(DependsStudyPlanWhitelist)]


@router.get(
    '/today',
    summary='获取今日计划',
    response_model=ResponseSchemaModel[TodayStudyPlanDetail],
    dependencies=STUDY_PLAN_WHITELIST_DEPENDENCIES,
)
async def study_plan_get_today(request: Request, db: CurrentSession) -> ResponseSchemaModel[TodayStudyPlanDetail]:
    detail = await get_today_plan(db, request.user.id)
    return response_base.success(data=detail)


@router.get(
    '/ability-catalog',
    summary='能力练习目录',
    response_model=ResponseSchemaModel[list[GetStudyPlanAbilityCatalogItem]],
)
async def study_plan_get_ability_catalog(
    db: CurrentSession,
    domain: str | None = Query(default=None, description='业务领域'),
) -> ResponseSchemaModel[list[GetStudyPlanAbilityCatalogItem]]:
    catalog = await list_ability_catalog_with_db(
        db,
        domain=domain,
        include_inactive=False,
    )
    return response_base.success(data=catalog)


@router.post(
    '/ability-attempts',
    summary='提交能力练习记录',
    response_model=ResponseSchemaModel[SubmitStudyAbilityAttemptResult],
)
async def study_plan_submit_ability_attempt(
    request: Request,
    db: CurrentSessionTransaction,
    param: SubmitStudyAbilityAttemptParam,
) -> ResponseSchemaModel[SubmitStudyAbilityAttemptResult]:
    result = await submit_ability_attempt(db, request.user.id, param)
    return response_base.success(data=result)


@router.post(
    '/ability-attempts/batch-sync',
    summary='批量同步能力练习记录',
    response_model=ResponseSchemaModel[BatchSubmitStudyAbilityAttemptResult],
)
async def study_plan_batch_sync_ability_attempts(
    request: Request,
    db: CurrentSessionTransaction,
    param: BatchSubmitStudyAbilityAttemptParam,
) -> ResponseSchemaModel[BatchSubmitStudyAbilityAttemptResult]:
    result = await batch_submit_ability_attempts(db, request.user.id, param)
    return response_base.success(data=result)


@router.get(
    '/ability-attempts',
    summary='我的能力练习历史列表',
    response_model=ResponseSchemaModel[list[GetStudyAbilityAttemptListItem]],
)
async def study_plan_list_my_ability_attempts(
    request: Request,
    db: CurrentSession,
    response: Response,
    ability_key: str | None = Query(default=None, description='能力标识过滤'),
    source: str | None = Query(default=None, description='来源过滤'),
    mode: str | None = Query(default=None, description='练习模式过滤'),
    start: date | None = Query(default=None, description='完成日期起始'),
    end: date | None = Query(default=None, description='完成日期截止'),
    offset: int = Query(default=0, ge=0, description='偏移量'),
    limit: int = Query(default=20, ge=1, le=100, description='每页数量'),
) -> ResponseSchemaModel[list[GetStudyAbilityAttemptListItem]]:
    items, total = await list_user_attempts(
        db,
        request.user.id,
        ability_key=ability_key,
        source=source,
        mode=mode,
        start=start,
        end=end,
        offset=offset,
        limit=limit,
    )
    response.headers['X-Total-Count'] = str(total)
    return response_base.success(data=items)


@router.get(
    '/ability-attempts/{client_session_id}',
    summary='能力练习记录详情',
    response_model=ResponseSchemaModel[GetStudyAbilityAttemptDetail],
)
async def study_plan_get_ability_attempt_detail(
    request: Request,
    db: CurrentSession,
    client_session_id: str = Path(description='客户端会话 ID'),
) -> ResponseSchemaModel[GetStudyAbilityAttemptDetail]:
    detail = await get_user_attempt_detail(db, request.user.id, client_session_id)
    return response_base.success(data=detail)


@router.get(
    '/ability-profile',
    summary='我的能力画像',
    response_model=ResponseSchemaModel[list[GetStudyUserCategoryProfileDetail]],
)
async def study_plan_get_ability_profile(
    request: Request,
    db: CurrentSession,
    source_type: str | None = Query(default='ability', description='来源类型'),
    category_id: int | None = Query(default=None, description='分类 ID'),
    include_children: bool = Query(default=True, description='是否包含子孙分类'),
) -> ResponseSchemaModel[list[GetStudyUserCategoryProfileDetail]]:
    profiles = await list_user_category_profiles(
        db,
        request.user.id,
        source_type,
        category_id,
        include_children,
    )
    return response_base.success(data=profiles)


@router.get(
    '/items/{item_id}',
    summary='获取计划项详情',
    response_model=ResponseSchemaModel[GetStudyPlanItemDetail],
    dependencies=STUDY_PLAN_WHITELIST_DEPENDENCIES,
)
async def study_plan_get_item(
    request: Request,
    db: CurrentSession,
    item_id: int = Path(description='计划项 ID'),
) -> ResponseSchemaModel[GetStudyPlanItemDetail]:
    item = await get_item_for_user(db, item_id, request.user.id)
    return response_base.success(data=await build_item_detail(db, item))


@router.post(
    '/items/{item_id}/start',
    summary='启动计划项',
    response_model=ResponseSchemaModel[StartStudyPlanItemResult],
    dependencies=STUDY_PLAN_WHITELIST_DEPENDENCIES,
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
    dependencies=STUDY_PLAN_WHITELIST_DEPENDENCIES,
)
async def study_plan_complete(
    request: Request,
    db: CurrentSessionTransaction,
    param: CompleteStudyPlanItemParam,
    item_id: int = Path(description='计划项 ID'),
) -> ResponseSchemaModel[GetStudyPlanRecordDetail]:
    record = await complete_item(db, item_id, request.user.id, param)
    return response_base.success(data=GetStudyPlanRecordDetail.model_validate(record))


@router.get(
    '/me/plans',
    summary='我的计划列表',
    response_model=ResponseSchemaModel[list[GetStudyPlanDetail]],
    dependencies=STUDY_PLAN_WHITELIST_DEPENDENCIES,
)
async def study_plan_list_my_plans(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetStudyPlanDetail]]:
    plans = await study_plan_dao.list_by_user(db, request.user.id)
    return response_base.success(
        data=[GetStudyPlanDetail.model_validate(p) for p in plans],
    )


@router.get(
    '/me/uncompleted-count',
    summary='历史未完成项数量（提醒铃铛）',
    response_model=ResponseSchemaModel[int],
    dependencies=STUDY_PLAN_WHITELIST_DEPENDENCIES,
)
async def study_plan_my_uncompleted_count(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[int]:
    count = await count_uncompleted_history(db, request.user.id)
    return response_base.success(data=count)


@router.get(
    '/me/plans/{plan_id}/items',
    summary='我的某计划的所有 items（总体规划页）',
    response_model=ResponseSchemaModel[list[GetStudyPlanItemDetail]],
    dependencies=STUDY_PLAN_WHITELIST_DEPENDENCIES,
)
async def study_plan_list_my_plan_items(
    request: Request,
    db: CurrentSession,
    plan_id: int = Path(description='计划 ID'),
) -> ResponseSchemaModel[list[GetStudyPlanItemDetail]]:
    items = await list_items_of_my_plan(db, plan_id, request.user.id)
    return response_base.success(
        data=await build_item_details(db, items),
    )


@router.get(
    '/me/plans/{plan_id}/progress',
    summary='我的某计划的进度（总体规划页顶部）',
    response_model=ResponseSchemaModel[StudyPlanProgress],
    dependencies=STUDY_PLAN_WHITELIST_DEPENDENCIES,
)
async def study_plan_my_plan_progress(
    request: Request,
    db: CurrentSession,
    plan_id: int = Path(description='计划 ID'),
) -> ResponseSchemaModel[StudyPlanProgress]:
    progress = await get_plan_progress_for_user(db, plan_id, request.user.id)
    return response_base.success(data=StudyPlanProgress(**progress))
