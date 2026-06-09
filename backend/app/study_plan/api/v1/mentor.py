#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy import select

from backend.app.study_plan.crud import (
    study_plan_dao,
    study_plan_item_dao,
)
from backend.app.study_plan.model.plan import StudyPlan
from backend.app.study_plan.schema.item import GetStudyPlanItemDetail
from backend.app.study_plan.schema.plan import (
    CreateStudyPlanParam,
    GetStudyPlanDetail,
    StudyPlanProgress,
)
from backend.app.study_plan.schema.template import InstantiateStudyPlanTemplateParam
from backend.app.study_plan.service.template_service import instantiate_template
from backend.common.exception import errors
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.post(
    '/plans/from-template',
    summary='基于模板为学员创建计划',
    response_model=ResponseSchemaModel[GetStudyPlanDetail],
    dependencies=[
        Depends(RequestPermission('study_plan:mentor:write')),
        DependsRBAC,
    ],
)
async def create_plan_from_template(
    request: Request,
    db: CurrentSessionTransaction,
    param: InstantiateStudyPlanTemplateParam,
) -> ResponseSchemaModel[GetStudyPlanDetail]:
    plan = await instantiate_template(db, param, creator_id=request.user.id)
    return response_base.success(data=GetStudyPlanDetail.model_validate(plan))


@router.post(
    '/plans',
    summary='创建空计划（导师后续手工添加 items）',
    response_model=ResponseSchemaModel[GetStudyPlanDetail],
    dependencies=[
        Depends(RequestPermission('study_plan:mentor:write')),
        DependsRBAC,
    ],
)
async def create_blank_plan(
    request: Request,
    db: CurrentSessionTransaction,
    param: CreateStudyPlanParam,
) -> ResponseSchemaModel[GetStudyPlanDetail]:
    plan = StudyPlan(
        user_id=param.user_id,
        title=param.title,
        start_date=param.start_date,
        end_date=param.end_date,
        domain=param.domain,
        status='active',
        template_id=param.template_id,
        created_by=request.user.id,
    )
    db.add(plan)
    await db.flush()
    return response_base.success(data=GetStudyPlanDetail.model_validate(plan))


@router.get(
    '/plans',
    summary='查询学员计划列表（导师视角）',
    response_model=ResponseSchemaModel[list[GetStudyPlanDetail]],
    dependencies=[
        Depends(RequestPermission('study_plan:mentor:read')),
        DependsRBAC,
    ],
)
async def list_plans_for_student(
    db: CurrentSession,
    student_id: int = Query(description='学员用户 ID'),
) -> ResponseSchemaModel[list[GetStudyPlanDetail]]:
    plans = await study_plan_dao.list_by_user(db, student_id)
    return response_base.success(
        data=[GetStudyPlanDetail.model_validate(p) for p in plans],
    )


@router.get(
    '/plans/{plan_id}/progress',
    summary='查询学员某计划的完成进度',
    response_model=ResponseSchemaModel[StudyPlanProgress],
    dependencies=[
        Depends(RequestPermission('study_plan:mentor:read')),
        DependsRBAC,
    ],
)
async def get_plan_progress(
    db: CurrentSession,
    plan_id: int = Path(description='计划 ID'),
) -> ResponseSchemaModel[StudyPlanProgress]:
    plan = await study_plan_dao.get(db, plan_id)
    if plan is None:
        raise errors.NotFoundError(msg='计划不存在')
    items = await study_plan_item_dao.list_by_plan(db, plan_id)
    completed = sum(1 for it in items if it.status == 'completed')
    total = len(items)
    percent = int(completed * 100 / total) if total else 0
    return response_base.success(
        data=StudyPlanProgress(completed=completed, total=total, percent=percent),
    )


@router.get(
    '/plans/{plan_id}/items',
    summary='查询学员某计划的所有 items',
    response_model=ResponseSchemaModel[list[GetStudyPlanItemDetail]],
    dependencies=[
        Depends(RequestPermission('study_plan:mentor:read')),
        DependsRBAC,
    ],
)
async def list_items_of_plan(
    db: CurrentSession,
    plan_id: int = Path(description='计划 ID'),
) -> ResponseSchemaModel[list[GetStudyPlanItemDetail]]:
    items = await study_plan_item_dao.list_by_plan(db, plan_id)
    return response_base.success(
        data=[GetStudyPlanItemDetail.model_validate(it) for it in items],
    )
