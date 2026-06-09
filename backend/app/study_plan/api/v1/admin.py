#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, Path, Request

from backend.app.study_plan.crud import (
    study_mentor_student_dao,
    study_plan_item_dao,
    study_plan_template_dao,
    study_plan_template_item_dao,
)
from backend.app.study_plan.model.item import StudyPlanItem
from backend.app.study_plan.model.mentor import StudyMentorStudent
from backend.app.study_plan.model.template import StudyPlanTemplate, StudyPlanTemplateItem
from backend.app.study_plan.schema.item import (
    CreateStudyPlanItemParam,
    GetStudyPlanItemDetail,
    UpdateStudyPlanItemParam,
)
from backend.app.study_plan.schema.mentor import (
    AssignMentorStudentParam,
    GetMentorStudentDetail,
    UpdateMentorStudentStatusParam,
)
from backend.app.study_plan.schema.template import (
    CreateStudyPlanTemplateParam,
    GetStudyPlanTemplateDetail,
    GetStudyPlanTemplateItemDetail,
    GetStudyPlanTemplateWithItemsDetail,
    UpdateStudyPlanTemplateParam,
)
from backend.common.exception import errors
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.post(
    '/items',
    summary='新增计划项',
    response_model=ResponseSchemaModel[GetStudyPlanItemDetail],
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_add_item(
    request: Request,
    db: CurrentSessionTransaction,
    param: CreateStudyPlanItemParam,
) -> ResponseSchemaModel[GetStudyPlanItemDetail]:
    item = StudyPlanItem(
        plan_id=param.plan_id,
        user_id=0,
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
    from backend.app.study_plan.crud import study_plan_dao

    plan = await study_plan_dao.get(db, param.plan_id)
    if plan is None:
        raise errors.NotFoundError(msg='所属计划不存在')
    item.user_id = plan.user_id

    db.add(item)
    await db.flush()
    return response_base.success(data=GetStudyPlanItemDetail.model_validate(item))


@router.put(
    '/items/{item_id}',
    summary='编辑计划项',
    response_model=ResponseSchemaModel[GetStudyPlanItemDetail],
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_update_item(
    db: CurrentSessionTransaction,
    param: UpdateStudyPlanItemParam,
    item_id: int = Path(description='计划项 ID'),
) -> ResponseSchemaModel[GetStudyPlanItemDetail]:
    item = await study_plan_item_dao.get(db, item_id)
    if item is None:
        raise errors.NotFoundError(msg='计划项不存在')
    fields = param.model_dump(exclude_unset=True)
    if not fields:
        return response_base.success(data=GetStudyPlanItemDetail.model_validate(item))
    await study_plan_item_dao.update_model(db, item_id, fields)
    refreshed = await study_plan_item_dao.get(db, item_id)
    return response_base.success(data=GetStudyPlanItemDetail.model_validate(refreshed))


@router.delete(
    '/items/{item_id}',
    summary='删除计划项',
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_delete_item(
    db: CurrentSessionTransaction,
    item_id: int = Path(description='计划项 ID'),
) -> ResponseModel:
    item = await study_plan_item_dao.get(db, item_id)
    if item is None:
        raise errors.NotFoundError(msg='计划项不存在')
    await study_plan_item_dao.delete_model(db, item_id)
    return response_base.success()


@router.post(
    '/templates',
    summary='创建计划模板（含模板项）',
    response_model=ResponseSchemaModel[GetStudyPlanTemplateDetail],
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_create_template(
    request: Request,
    db: CurrentSessionTransaction,
    param: CreateStudyPlanTemplateParam,
) -> ResponseSchemaModel[GetStudyPlanTemplateDetail]:
    tpl = StudyPlanTemplate(
        name=param.name,
        duration_days=param.duration_days,
        domain=param.domain,
        description=param.description,
        is_active=param.is_active,
        created_by=request.user.id,
    )
    db.add(tpl)
    await db.flush()

    if param.items:
        items = [
            StudyPlanTemplateItem(
                template_id=tpl.id,
                day_index=ti.day_index,
                order_index=ti.order_index,
                module_type=ti.module_type,
                title=ti.title,
                ref_type=ti.ref_type,
                ref_id=ti.ref_id,
                expected_minutes=ti.expected_minutes,
                extra=ti.extra,
            )
            for ti in param.items
        ]
        db.add_all(items)
        await db.flush()
    return response_base.success(data=GetStudyPlanTemplateDetail.model_validate(tpl))


@router.put(
    '/templates/{template_id}',
    summary='更新计划模板',
    response_model=ResponseSchemaModel[GetStudyPlanTemplateDetail],
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_update_template(
    db: CurrentSessionTransaction,
    param: UpdateStudyPlanTemplateParam,
    template_id: int = Path(description='模板 ID'),
) -> ResponseSchemaModel[GetStudyPlanTemplateDetail]:
    tpl = await study_plan_template_dao.get(db, template_id)
    if tpl is None:
        raise errors.NotFoundError(msg='模板不存在')
    fields = param.model_dump(exclude_unset=True)
    if fields:
        await study_plan_template_dao.update_model(db, template_id, fields)
    refreshed = await study_plan_template_dao.get(db, template_id)
    return response_base.success(data=GetStudyPlanTemplateDetail.model_validate(refreshed))


@router.get(
    '/templates',
    summary='模板列表（按 domain 过滤）',
    response_model=ResponseSchemaModel[list[GetStudyPlanTemplateDetail]],
    dependencies=[Depends(RequestPermission('study_plan:admin:read')), DependsRBAC],
)
async def study_plan_list_templates(
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetStudyPlanTemplateDetail]]:
    tpls = await study_plan_template_dao.list_active(db)
    return response_base.success(
        data=[GetStudyPlanTemplateDetail.model_validate(t) for t in tpls],
    )


@router.get(
    '/templates/{template_id}',
    summary='模板详情（含模板项）',
    response_model=ResponseSchemaModel[GetStudyPlanTemplateWithItemsDetail],
    dependencies=[Depends(RequestPermission('study_plan:admin:read')), DependsRBAC],
)
async def study_plan_get_template(
    db: CurrentSession,
    template_id: int = Path(description='模板 ID'),
) -> ResponseSchemaModel[GetStudyPlanTemplateWithItemsDetail]:
    tpl = await study_plan_template_dao.get(db, template_id)
    if tpl is None:
        raise errors.NotFoundError(msg='模板不存在')
    items = await study_plan_template_item_dao.list_by_template(db, template_id)
    detail = GetStudyPlanTemplateWithItemsDetail.model_validate(tpl)
    detail.items = [GetStudyPlanTemplateItemDetail.model_validate(it) for it in items]
    return response_base.success(data=detail)


@router.post(
    '/mentors/assign',
    summary='管理员分配导师与学员',
    response_model=ResponseSchemaModel[GetMentorStudentDetail],
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_assign_mentor_student(
    request: Request,
    db: CurrentSessionTransaction,
    param: AssignMentorStudentParam,
) -> ResponseSchemaModel[GetMentorStudentDetail]:
    if param.mentor_id == param.student_id:
        raise errors.RequestError(msg='导师与学员不能是同一人')
    existing = await study_mentor_student_dao.get_pair(db, param.mentor_id, param.student_id)
    if existing is not None:
        raise errors.ConflictError(msg='该导师与学员已分配')
    relation = StudyMentorStudent(
        mentor_id=param.mentor_id,
        student_id=param.student_id,
        assigned_by=request.user.id,
        status='active',
        note=param.note,
    )
    db.add(relation)
    await db.flush()
    return response_base.success(data=GetMentorStudentDetail.model_validate(relation))


@router.put(
    '/mentors/{relation_id}/status',
    summary='更新导师学员关系状态',
    response_model=ResponseSchemaModel[GetMentorStudentDetail],
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_update_mentor_student_status(
    db: CurrentSessionTransaction,
    param: UpdateMentorStudentStatusParam,
    relation_id: int = Path(description='关系 ID'),
) -> ResponseSchemaModel[GetMentorStudentDetail]:
    relation = await study_mentor_student_dao.get(db, relation_id)
    if relation is None:
        raise errors.NotFoundError(msg='关系不存在')
    await study_mentor_student_dao.update_model(db, relation_id, {'status': param.status})
    refreshed = await study_mentor_student_dao.get(db, relation_id)
    return response_base.success(data=GetMentorStudentDetail.model_validate(refreshed))
