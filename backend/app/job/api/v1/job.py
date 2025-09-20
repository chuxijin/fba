#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path

from backend.app.job.schema.job import (
    CreateJobPostingParam,
    DeleteJobPostingParam,
    JobPostingDetail,
    JobSearchParam,
    UpdateJobPostingParam,
)
from backend.app.job.service.job import JobService
from backend.common.pagination import PageData, DependsPagination, _CustomPageParams
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC


router = APIRouter(prefix='/jobs', tags=['岗位管理'])


@router.get(
    '',
    summary='分页查询岗位',
    dependencies=[Depends(RequestPermission('job.jobs.query')), DependsRBAC],
)
async def get_jobs_paged(
    params: Annotated[JobSearchParam, Depends()],
    page_params: Annotated[_CustomPageParams, DependsPagination],
) -> ResponseSchemaModel[PageData[JobPostingDetail]]:
    page_data = await JobService.get_paged_list(params)
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='创建岗位',
    dependencies=[Depends(RequestPermission('job.jobs.create')), DependsRBAC],
)
async def create_job(
    obj: CreateJobPostingParam,
) -> ResponseSchemaModel[str]:
    await JobService.create(obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新岗位',
    dependencies=[Depends(RequestPermission('job.jobs.update')), DependsRBAC],
)
async def update_job(
    pk: Annotated[int, Path(description='岗位 ID')],
    obj: UpdateJobPostingParam,
) -> ResponseSchemaModel[int]:
    rows = await JobService.update(pk, obj)
    return response_base.success(data=rows)


@router.delete(
    '',
    summary='批量删除岗位',
    dependencies=[Depends(RequestPermission('job.jobs.delete')), DependsRBAC],
)
async def delete_jobs(
    objs: DeleteJobPostingParam,
) -> ResponseSchemaModel[int]:
    rows = await JobService.delete(objs)
    return response_base.success(data=rows)


