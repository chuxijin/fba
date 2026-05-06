#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.job.schema.job_posting import (
    CreateJobPosting,
    DeleteJobPostingParam,
    JobPostingSchema,
    UpdateJobPosting,
)
from backend.app.job.service.job_posting_service import job_posting_service
from backend.common.enums import ApplicationStatus
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('/all', summary='获取所有招聘信息', dependencies=[DependsJwtAuth])
async def get_all_job_postings() -> ResponseSchemaModel[list[JobPostingSchema]]:
    data = await job_posting_service.get_all()
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取招聘信息详情', dependencies=[DependsJwtAuth])
async def get_job_posting(pk: Annotated[int, Path(description='招聘信息 ID')]) -> ResponseSchemaModel[JobPostingSchema]:
    data = await job_posting_service.get(pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页获取招聘信息列表',
    dependencies=[
        DependsJwtAuth,
        DependsPagination,
    ],
)
async def get_job_postings_paged(
    db: CurrentSession,
    request: Request,
    company_name: Annotated[str | None, Query(description='公司名称')] = None,
    company_type: Annotated[str | None, Query(description='公司类型')] = None,
    work_location: Annotated[str | None, Query(description='工作地点')] = None,
    recruitment_object: Annotated[str | None, Query(description='招聘对象')] = None,
    position: Annotated[str | None, Query(description='岗位')] = None,
    industry: Annotated[str | None, Query(description='所属行业')] = None,
    recruitment_type: Annotated[str | None, Query(description='招聘类型')] = None,
    application_status: Annotated[ApplicationStatus | None, Query(description='我的投递状态')] = None,
) -> ResponseSchemaModel[PageData[JobPostingSchema]]:
    job_posting_select = await job_posting_service.get_select(
        company_name=company_name,
        position=position,
        industry=industry,
        recruitment_type=recruitment_type,
        company_type=company_type,
        work_location=work_location,
        recruitment_object=recruitment_object,
        application_status=application_status,
        user_id=request.user.id,
    )
    page_data = await paging_data(db, job_posting_select)
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='创建招聘信息',
    dependencies=[
        Depends(RequestPermission('sys:job:posting:add')),
        DependsRBAC,
    ],
)
async def create_job_posting(obj: CreateJobPosting, request: Request) -> ResponseModel:
    await job_posting_service.create(obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新招聘信息',
    dependencies=[
        Depends(RequestPermission('sys:job:posting:edit')),
        DependsRBAC,
    ],
)
async def update_job_posting(pk: Annotated[int, Path(description='招聘信息 ID')], obj: UpdateJobPosting) -> ResponseModel:
    count = await job_posting_service.update(pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='批量删除招聘信息',
    dependencies=[
        Depends(RequestPermission('sys:job:posting:del')),
        DependsRBAC,
    ],
)
async def delete_job_postings(obj: DeleteJobPostingParam) -> ResponseModel:
    count = await job_posting_service.delete(obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
