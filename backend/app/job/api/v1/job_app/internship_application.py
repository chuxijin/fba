#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.job.schema.internship_application import (
    CreateInternshipApplication,
    DeleteInternshipApplicationParam,
    InternshipApplicationSchema,
    UpdateInternshipApplication,
)
from backend.app.job.service.internship_application_service import internship_application_service
from backend.common.enums import ApplicationStatus
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('/all', summary='获取所有投递记录', dependencies=[DependsJwtAuth])
async def get_all_internship_applications() -> ResponseSchemaModel[list[InternshipApplicationSchema]]:
    data = await internship_application_service.get_all()
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取投递记录详情', dependencies=[DependsJwtAuth])
async def get_internship_application(
    pk: Annotated[int, Path(description='投递记录 ID')],
    request: Request,
) -> ResponseSchemaModel[InternshipApplicationSchema]:
    data = await internship_application_service.get(pk=pk, user_id=request.user.id)
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页获取投递记录列表',
    dependencies=[
        DependsJwtAuth,
        DependsPagination,
    ],
)
async def get_internship_applications_paged(
    db: CurrentSession,
    request: Request,
    job_posting_id: Annotated[int | None, Query(description='招聘信息 ID')] = None,
    application_status: Annotated[ApplicationStatus | None, Query(description='投递状态')] = None,
        ) -> ResponseSchemaModel[PageData[InternshipApplicationSchema]]:
    job_application_select = await internship_application_service.get_select(
        user_id=request.user.id,
        job_posting_id=job_posting_id,
        application_status=application_status
    )
    page_data = await paging_data(db, job_application_select)
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='创建投递记录',
    dependencies=[
        Depends(RequestPermission('job:application:add')),
        DependsRBAC,
    ],
)
async def create_internship_application(obj: CreateInternshipApplication, request: Request) -> ResponseModel:
    await internship_application_service.create(obj=obj, user_id=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新投递记录',
    dependencies=[
        Depends(RequestPermission('job:application:edit')),
        DependsRBAC,
    ],
)
async def update_internship_application(
    pk: Annotated[int, Path(description='投递记录 ID')], 
    obj: UpdateInternshipApplication, 
    request: Request
) -> ResponseModel:
    count = await internship_application_service.update(pk=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='批量删除投递记录',
    dependencies=[
        Depends(RequestPermission('job:application:del')),
        DependsRBAC,
    ],
)
async def delete_internship_applications(obj: DeleteInternshipApplicationParam, request: Request) -> ResponseModel:
    count = await internship_application_service.delete(obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()
