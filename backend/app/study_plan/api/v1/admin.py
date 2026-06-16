#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.study_plan.crud import (
    study_mentor_student_dao,
    study_plan_item_dao,
    study_plan_template_dao,
    study_plan_template_item_dao,
)
from backend.app.study_plan.model.item import StudyPlanItem
from backend.app.study_plan.model.mentor import StudyMentorStudent
from backend.app.study_plan.model.template import StudyPlanTemplate, StudyPlanTemplateItem
from backend.app.study_plan.schema.ability import (
    CreateStudyAbilityCatalogParam,
    CreateStudyAbilityCategoryBindingParam,
    GetStudyAbilityCategoryBindingDetail,
    GetStudyPlanAbilityCatalogItem,
    UpdateStudyAbilityCatalogParam,
    UpdateStudyAbilityCategoryBindingParam,
)
from backend.app.study_plan.schema.item import (
    CreateStudyPlanItemParam,
    GetStudyPlanItemDetail,
    UpdateStudyPlanItemParam,
)
from backend.app.study_plan.schema.mentor import (
    AssignMentorStudentParam,
    GetMentorStudentDetail,
    MentorStatus,
    UpdateMentorStudentStatusParam,
)
from backend.app.study_plan.schema.practice_source import (
    PreviewStudyPlanPracticeSourceParam,
    PreviewStudyPlanPracticeSourceResult,
)
from backend.app.study_plan.schema.template import (
    CreateStudyPlanTemplateParam,
    CreateStudyPlanTemplateItemParam,
    GetStudyPlanTemplateDetail,
    GetStudyPlanTemplateItemDetail,
    GetStudyPlanTemplateWithItemsDetail,
    UpdateStudyPlanTemplateParam,
    UpdateStudyPlanTemplateItemParam,
)
from backend.app.study_plan.service.ability_catalog import (
    create_ability_binding,
    create_ability_catalog,
    delete_ability_binding,
    delete_ability_catalog,
    list_ability_bindings,
    list_ability_catalog_with_db,
    update_ability_binding,
    update_ability_catalog,
)
from backend.app.study_plan.service.ability_url_resolver import enrich_ability_item_extra
from backend.app.study_plan.service.item_detail_service import build_item_detail
from backend.app.study_plan.service.practice_source import preview_practice_source
from backend.common.exception import errors
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/ability-catalog',
    summary='能力练习目录',
    response_model=ResponseSchemaModel[list[GetStudyPlanAbilityCatalogItem]],
    dependencies=[Depends(RequestPermission('study_plan:admin:read')), DependsRBAC],
)
async def study_plan_list_ability_catalog(
    db: CurrentSession,
    domain: str | None = Query(default=None, description='业务领域'),
    keyword: str | None = Query(default=None, description='关键词'),
    include_inactive: bool = Query(default=True, description='是否包含停用项'),
) -> ResponseSchemaModel[list[GetStudyPlanAbilityCatalogItem]]:
    catalog = await list_ability_catalog_with_db(
        db,
        domain=domain,
        keyword=keyword,
        include_inactive=include_inactive,
    )
    return response_base.success(data=catalog)


@router.post(
    '/ability-catalog',
    summary='新增能力练习目录',
    response_model=ResponseSchemaModel[GetStudyPlanAbilityCatalogItem],
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_create_ability_catalog(
    request: Request,
    db: CurrentSessionTransaction,
    param: CreateStudyAbilityCatalogParam,
) -> ResponseSchemaModel[GetStudyPlanAbilityCatalogItem]:
    catalog = await create_ability_catalog(db, param, request.user.id)
    return response_base.success(data=catalog)


@router.put(
    '/ability-catalog/{catalog_id}',
    summary='编辑能力练习目录',
    response_model=ResponseSchemaModel[GetStudyPlanAbilityCatalogItem],
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_update_ability_catalog(
    request: Request,
    db: CurrentSessionTransaction,
    param: UpdateStudyAbilityCatalogParam,
    catalog_id: int = Path(description='目录 ID'),
) -> ResponseSchemaModel[GetStudyPlanAbilityCatalogItem]:
    catalog = await update_ability_catalog(db, catalog_id, param, request.user.id)
    return response_base.success(data=catalog)


@router.delete(
    '/ability-catalog/{catalog_id}',
    summary='删除能力练习目录',
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_delete_ability_catalog(
    db: CurrentSessionTransaction,
    catalog_id: int = Path(description='目录 ID'),
) -> ResponseModel:
    await delete_ability_catalog(db, catalog_id)
    return response_base.success()


@router.get(
    '/ability-bindings',
    summary='能力分类绑定列表',
    response_model=ResponseSchemaModel[list[GetStudyAbilityCategoryBindingDetail]],
    dependencies=[Depends(RequestPermission('study_plan:admin:read')), DependsRBAC],
)
async def study_plan_list_ability_bindings(
    db: CurrentSession,
    ability_key: str | None = Query(default=None, description='能力标识'),
    category_id: int | None = Query(default=None, description='分类 ID'),
    role: str | None = Query(default=None, description='绑定角色'),
) -> ResponseSchemaModel[list[GetStudyAbilityCategoryBindingDetail]]:
    bindings = await list_ability_bindings(db, ability_key=ability_key, category_id=category_id, role=role)
    return response_base.success(data=bindings)


@router.post(
    '/ability-bindings',
    summary='新增能力分类绑定',
    response_model=ResponseSchemaModel[GetStudyAbilityCategoryBindingDetail],
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_create_ability_binding(
    request: Request,
    db: CurrentSessionTransaction,
    param: CreateStudyAbilityCategoryBindingParam,
) -> ResponseSchemaModel[GetStudyAbilityCategoryBindingDetail]:
    binding = await create_ability_binding(db, param, request.user.id)
    return response_base.success(data=binding)


@router.put(
    '/ability-bindings/{binding_id}',
    summary='编辑能力分类绑定',
    response_model=ResponseSchemaModel[GetStudyAbilityCategoryBindingDetail],
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_update_ability_binding(
    request: Request,
    db: CurrentSessionTransaction,
    param: UpdateStudyAbilityCategoryBindingParam,
    binding_id: int = Path(description='绑定 ID'),
) -> ResponseSchemaModel[GetStudyAbilityCategoryBindingDetail]:
    binding = await update_ability_binding(db, binding_id, param, request.user.id)
    return response_base.success(data=binding)


@router.delete(
    '/ability-bindings/{binding_id}',
    summary='删除能力分类绑定',
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_delete_ability_binding(
    db: CurrentSessionTransaction,
    binding_id: int = Path(description='绑定 ID'),
) -> ResponseModel:
    await delete_ability_binding(db, binding_id)
    return response_base.success()


@router.post(
    '/practice-sources/preview',
    summary='预览刷题来源题量',
    response_model=ResponseSchemaModel[PreviewStudyPlanPracticeSourceResult],
    dependencies=[Depends(RequestPermission('study_plan:admin:read')), DependsRBAC],
)
async def study_plan_preview_practice_source(
    db: CurrentSession,
    param: PreviewStudyPlanPracticeSourceParam,
) -> ResponseSchemaModel[PreviewStudyPlanPracticeSourceResult]:
    result = await preview_practice_source(db, param)
    return response_base.success(data=result)


@router.get(
    '/mentors',
    summary='查询导师学员关系列表',
    response_model=ResponseSchemaModel[list[GetMentorStudentDetail]],
    dependencies=[Depends(RequestPermission('study_plan:admin:read')), DependsRBAC],
)
async def study_plan_list_mentor_students(
    db: CurrentSession,
    mentor_id: int | None = Query(default=None, description='导师用户 ID'),
    student_id: int | None = Query(default=None, description='学员用户 ID'),
    status: MentorStatus | None = Query(default=None, description='关系状态'),
) -> ResponseSchemaModel[list[GetMentorStudentDetail]]:
    relations = await study_mentor_student_dao.list_relations(
        db,
        mentor_id=mentor_id,
        student_id=student_id,
        status=status,
    )
    return response_base.success(
        data=[GetMentorStudentDetail.model_validate(relation) for relation in relations],
    )


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
    enriched_extra = await enrich_ability_item_extra(db, param.extra)
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
        extra=enriched_extra,
        created_by=request.user.id,
    )
    from backend.app.study_plan.crud import study_plan_dao

    plan = await study_plan_dao.get(db, param.plan_id)
    if plan is None:
        raise errors.NotFoundError(msg='所属计划不存在')
    item.user_id = plan.user_id

    db.add(item)
    await db.flush()
    return response_base.success(data=await build_item_detail(db, item))


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
        return response_base.success(data=await build_item_detail(db, item))
    if 'extra' in fields and fields['extra']:
        fields['extra'] = await enrich_ability_item_extra(db, fields['extra'])
    await study_plan_item_dao.update_model(db, item_id, fields)
    refreshed = await study_plan_item_dao.get(db, item_id)
    return response_base.success(data=await build_item_detail(db, refreshed))


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
        items = []
        for ti in param.items:
            enriched_extra = await enrich_ability_item_extra(db, ti.extra)
            items.append(StudyPlanTemplateItem(
                template_id=tpl.id,
                day_index=ti.day_index,
                order_index=ti.order_index,
                module_type=ti.module_type,
                title=ti.title,
                ref_type=ti.ref_type,
                ref_id=ti.ref_id,
                expected_minutes=ti.expected_minutes,
                extra=enriched_extra,
            ))
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


@router.post(
    '/templates/{template_id}/items',
    summary='新增模板项',
    response_model=ResponseSchemaModel[GetStudyPlanTemplateItemDetail],
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_add_template_item(
    db: CurrentSessionTransaction,
    param: CreateStudyPlanTemplateItemParam,
    template_id: int = Path(description='模板 ID'),
) -> ResponseSchemaModel[GetStudyPlanTemplateItemDetail]:
    tpl = await study_plan_template_dao.get(db, template_id)
    if tpl is None:
        raise errors.NotFoundError(msg='模板不存在')

    item = StudyPlanTemplateItem(
        template_id=template_id,
        day_index=param.day_index,
        order_index=param.order_index,
        module_type=param.module_type,
        title=param.title,
        ref_type=param.ref_type,
        ref_id=param.ref_id,
        expected_minutes=param.expected_minutes,
        extra=await enrich_ability_item_extra(db, param.extra),
    )
    db.add(item)
    await db.flush()
    return response_base.success(data=GetStudyPlanTemplateItemDetail.model_validate(item))


@router.put(
    '/template-items/{item_id}',
    summary='编辑模板项',
    response_model=ResponseSchemaModel[GetStudyPlanTemplateItemDetail],
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_update_template_item(
    db: CurrentSessionTransaction,
    param: UpdateStudyPlanTemplateItemParam,
    item_id: int = Path(description='模板项 ID'),
) -> ResponseSchemaModel[GetStudyPlanTemplateItemDetail]:
    item = await study_plan_template_item_dao.get(db, item_id)
    if item is None:
        raise errors.NotFoundError(msg='模板项不存在')

    fields = param.model_dump(exclude_unset=True)
    if not fields:
        return response_base.success(data=GetStudyPlanTemplateItemDetail.model_validate(item))

    if 'extra' in fields and fields['extra']:
        fields['extra'] = await enrich_ability_item_extra(db, fields['extra'])
    await study_plan_template_item_dao.update_model(db, item_id, fields)
    refreshed = await study_plan_template_item_dao.get(db, item_id)
    return response_base.success(data=GetStudyPlanTemplateItemDetail.model_validate(refreshed))


@router.delete(
    '/template-items/{item_id}',
    summary='删除模板项',
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def study_plan_delete_template_item(
    db: CurrentSessionTransaction,
    item_id: int = Path(description='模板项 ID'),
) -> ResponseModel:
    item = await study_plan_template_item_dao.get(db, item_id)
    if item is None:
        raise errors.NotFoundError(msg='模板项不存在')

    await study_plan_template_item_dao.delete_model(db, item_id)
    return response_base.success()


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
