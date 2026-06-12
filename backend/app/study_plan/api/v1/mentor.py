#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.study_plan.crud import (
    study_plan_dao,
    study_plan_item_dao,
)
from backend.app.study_plan.model.item import StudyPlanItem
from backend.app.study_plan.model.plan import StudyPlan
from backend.app.study_plan.schema.ability import GetStudyUserCategoryProfileDetail
from backend.app.study_plan.schema.item import (
    CreateStudyPlanItemParam,
    GetStudyPlanItemDetail,
    UpdateStudyPlanItemParam,
)
from backend.app.study_plan.schema.mentor import GetMentorStudentOption
from backend.app.study_plan.schema.plan import (
    CreateStudyPlanParam,
    GetStudyPlanDetail,
    StudyPlanProgress,
    UpdateStudyPlanParam,
)
from backend.app.study_plan.schema.recommendation import (
    GetStudyPlanItemRecommendation,
    RecommendationModuleType,
)
from backend.app.study_plan.schema.template import InstantiateStudyPlanTemplateParam
from backend.app.study_plan.service.ability_profile import list_user_category_profiles
from backend.app.study_plan.service.item_detail_service import build_item_detail, build_item_details
from backend.app.study_plan.service.mentor_service import (
    ensure_mentor_can_access_student,
    get_item_for_mentor,
    get_plan_for_mentor,
    list_accessible_students_for_mentor,
)
from backend.app.study_plan.service.recommendation_service import list_plan_item_recommendations
from backend.app.study_plan.service.template_service import instantiate_template
from backend.common.exception import errors
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/students',
    summary='查询当前导师可访问学员',
    response_model=ResponseSchemaModel[list[GetMentorStudentOption]],
    dependencies=[
        Depends(RequestPermission('study_plan:mentor:read')),
        DependsRBAC,
    ],
)
async def study_plan_list_accessible_students(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetMentorStudentOption]]:
    students = await list_accessible_students_for_mentor(
        db,
        request.user.id,
        request.user.is_superuser,
    )
    return response_base.success(data=students)


@router.post(
    '/plans/from-template',
    summary='基于模板为学员创建计划',
    response_model=ResponseSchemaModel[GetStudyPlanDetail],
    dependencies=[
        Depends(RequestPermission('study_plan:mentor:write')),
        DependsRBAC,
    ],
)
async def study_plan_create_plan_from_template(
    request: Request,
    db: CurrentSessionTransaction,
    param: InstantiateStudyPlanTemplateParam,
) -> ResponseSchemaModel[GetStudyPlanDetail]:
    await ensure_mentor_can_access_student(
        db,
        request.user.id,
        param.user_id,
        request.user.is_superuser,
    )
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
async def study_plan_create_blank_plan(
    request: Request,
    db: CurrentSessionTransaction,
    param: CreateStudyPlanParam,
) -> ResponseSchemaModel[GetStudyPlanDetail]:
    await ensure_mentor_can_access_student(
        db,
        request.user.id,
        param.user_id,
        request.user.is_superuser,
    )
    if param.end_date < param.start_date:
        raise errors.RequestError(msg='结束日期不能早于起始日期')

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
async def study_plan_list_plans_for_student(
    request: Request,
    db: CurrentSession,
    student_id: int = Query(description='学员用户 ID'),
) -> ResponseSchemaModel[list[GetStudyPlanDetail]]:
    await ensure_mentor_can_access_student(
        db,
        request.user.id,
        student_id,
        request.user.is_superuser,
    )
    plans = await study_plan_dao.list_by_user(db, student_id)
    return response_base.success(
        data=[GetStudyPlanDetail.model_validate(p) for p in plans],
    )


@router.get(
    '/students/{student_id}/ability-profile',
    summary='查询学员能力画像',
    response_model=ResponseSchemaModel[list[GetStudyUserCategoryProfileDetail]],
    dependencies=[
        Depends(RequestPermission('study_plan:mentor:read')),
        DependsRBAC,
    ],
)
async def study_plan_get_student_ability_profile(
    request: Request,
    db: CurrentSession,
    student_id: int = Path(description='学员用户 ID'),
    source_type: str | None = Query(default=None, description='来源类型'),
    category_id: int | None = Query(default=None, description='分类 ID'),
    include_children: bool = Query(default=True, description='是否包含子孙分类'),
) -> ResponseSchemaModel[list[GetStudyUserCategoryProfileDetail]]:
    await ensure_mentor_can_access_student(
        db,
        request.user.id,
        student_id,
        request.user.is_superuser,
    )
    profiles = await list_user_category_profiles(
        db,
        student_id,
        source_type,
        category_id,
        include_children,
    )
    return response_base.success(data=profiles)


@router.get(
    '/students/{student_id}/plan-item-recommendations',
    summary='查询画像驱动计划项推荐',
    response_model=ResponseSchemaModel[list[GetStudyPlanItemRecommendation]],
    dependencies=[
        Depends(RequestPermission('study_plan:mentor:read')),
        DependsRBAC,
    ],
)
async def study_plan_get_plan_item_recommendations(
    request: Request,
    db: CurrentSession,
    student_id: int = Path(description='学员用户 ID'),
    source_type: str | None = Query(default=None, description='画像来源'),
    category_id: int | None = Query(default=None, description='分类 ID'),
    include_children: bool = Query(default=True, description='是否包含子孙分类'),
    module_type: RecommendationModuleType | None = Query(default=None, description='推荐模块类型'),
    limit: int = Query(default=10, ge=1, le=50, description='返回数量'),
) -> ResponseSchemaModel[list[GetStudyPlanItemRecommendation]]:
    await ensure_mentor_can_access_student(
        db,
        request.user.id,
        student_id,
        request.user.is_superuser,
    )
    recommendations = await list_plan_item_recommendations(
        db,
        student_id,
        source_type=source_type,
        category_id=category_id,
        include_children=include_children,
        module_type=module_type,
        limit=limit,
    )
    return response_base.success(data=recommendations)


@router.put(
    '/plans/{plan_id}',
    summary='更新学习计划主信息',
    response_model=ResponseSchemaModel[GetStudyPlanDetail],
    dependencies=[
        Depends(RequestPermission('study_plan:mentor:write')),
        DependsRBAC,
    ],
)
async def study_plan_update_plan(
    request: Request,
    db: CurrentSessionTransaction,
    param: UpdateStudyPlanParam,
    plan_id: int = Path(description='计划 ID'),
) -> ResponseSchemaModel[GetStudyPlanDetail]:
    plan = await get_plan_for_mentor(
        db,
        plan_id,
        request.user.id,
        request.user.is_superuser,
    )

    fields = param.model_dump(exclude_unset=True)
    if not fields:
        return response_base.success(data=GetStudyPlanDetail.model_validate(plan))

    start_date = fields.get('start_date', plan.start_date)
    end_date = fields.get('end_date', plan.end_date)
    if end_date < start_date:
        raise errors.RequestError(msg='结束日期不能早于起始日期')

    await study_plan_dao.update_model(db, plan_id, fields)
    refreshed = await study_plan_dao.get(db, plan_id)
    return response_base.success(data=GetStudyPlanDetail.model_validate(refreshed))


@router.get(
    '/plans/{plan_id}/progress',
    summary='查询学员某计划的完成进度',
    response_model=ResponseSchemaModel[StudyPlanProgress],
    dependencies=[
        Depends(RequestPermission('study_plan:mentor:read')),
        DependsRBAC,
    ],
)
async def study_plan_get_plan_progress(
    request: Request,
    db: CurrentSession,
    plan_id: int = Path(description='计划 ID'),
) -> ResponseSchemaModel[StudyPlanProgress]:
    await get_plan_for_mentor(
        db,
        plan_id,
        request.user.id,
        request.user.is_superuser,
    )
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
async def study_plan_list_items_of_plan(
    request: Request,
    db: CurrentSession,
    plan_id: int = Path(description='计划 ID'),
) -> ResponseSchemaModel[list[GetStudyPlanItemDetail]]:
    await get_plan_for_mentor(
        db,
        plan_id,
        request.user.id,
        request.user.is_superuser,
    )
    items = await study_plan_item_dao.list_by_plan(db, plan_id)
    return response_base.success(
        data=await build_item_details(db, items),
    )


@router.post(
    '/items',
    summary='导师新增计划项',
    response_model=ResponseSchemaModel[GetStudyPlanItemDetail],
    dependencies=[
        Depends(RequestPermission('study_plan:mentor:write')),
        DependsRBAC,
    ],
)
async def study_plan_mentor_add_item(
    request: Request,
    db: CurrentSessionTransaction,
    param: CreateStudyPlanItemParam,
) -> ResponseSchemaModel[GetStudyPlanItemDetail]:
    plan = await get_plan_for_mentor(
        db,
        param.plan_id,
        request.user.id,
        request.user.is_superuser,
    )
    _ensure_item_date_within_plan(plan, param.plan_date)

    item = StudyPlanItem(
        plan_id=param.plan_id,
        user_id=plan.user_id,
        plan_date=param.plan_date,
        order_index=param.order_index,
        module_type=param.module_type,
        title=param.title,
        ref_type=param.ref_type,
        ref_id=param.ref_id,
        expected_minutes=param.expected_minutes,
        status='pending',
        extra=param.extra,
        created_by=request.user.id,
    )
    db.add(item)
    await db.flush()
    return response_base.success(data=await build_item_detail(db, item))


@router.put(
    '/items/{item_id}',
    summary='导师编辑计划项',
    response_model=ResponseSchemaModel[GetStudyPlanItemDetail],
    dependencies=[
        Depends(RequestPermission('study_plan:mentor:write')),
        DependsRBAC,
    ],
)
async def study_plan_mentor_update_item(
    request: Request,
    db: CurrentSessionTransaction,
    param: UpdateStudyPlanItemParam,
    item_id: int = Path(description='计划项 ID'),
) -> ResponseSchemaModel[GetStudyPlanItemDetail]:
    item = await get_item_for_mentor(
        db,
        item_id,
        request.user.id,
        request.user.is_superuser,
    )
    fields = param.model_dump(exclude_unset=True)
    if not fields:
        return response_base.success(data=await build_item_detail(db, item))

    if 'plan_date' in fields:
        plan = await get_plan_for_mentor(
            db,
            item.plan_id,
            request.user.id,
            request.user.is_superuser,
        )
        _ensure_item_date_within_plan(plan, fields['plan_date'])

    await study_plan_item_dao.update_model(db, item_id, fields)
    refreshed = await study_plan_item_dao.get(db, item_id)
    return response_base.success(data=await build_item_detail(db, refreshed))


@router.delete(
    '/items/{item_id}',
    summary='导师删除计划项',
    dependencies=[
        Depends(RequestPermission('study_plan:mentor:write')),
        DependsRBAC,
    ],
)
async def study_plan_mentor_delete_item(
    request: Request,
    db: CurrentSessionTransaction,
    item_id: int = Path(description='计划项 ID'),
) -> ResponseModel:
    await get_item_for_mentor(
        db,
        item_id,
        request.user.id,
        request.user.is_superuser,
    )
    await study_plan_item_dao.delete_model(db, item_id)
    return response_base.success()


def _ensure_item_date_within_plan(plan: StudyPlan, plan_date: date) -> None:
    """
    校验计划项日期是否落在计划周期内

    :param plan: 学习计划
    :param plan_date: 计划项日期
    :return:
    """
    if plan.start_date <= plan_date <= plan.end_date:
        return
    raise errors.RequestError(msg='计划项日期必须在计划周期内')
