from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request

from backend.app.job.schema.job_application import (
    CreateJobApplication,
    GetJobApplicationDetail,
    GetJobApplicationListParams,
    JobApplicationSchema,
    UpdateJobApplication,
)
from backend.app.job.service.job_application_service import job_application_service
from backend.database.db import CurrentSession
from backend.common.enums import ApplicationStatus
from backend.common.pagination import PageData, DependsPagination, _CustomPageParams
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth, get_current_user

router = APIRouter()


@router.post(
    "/job_application", summary="创建投递记录", response_model=ResponseSchemaModel[JobApplicationSchema], dependencies=[DependsJwtAuth]
)
async def create_job_application(
    obj_in: CreateJobApplication,
    db: CurrentSession,
    request: Request,
) -> ResponseSchemaModel[JobApplicationSchema]:
    job_application = await job_application_service.create(db, obj_in, request.user.id)
    return response_base.success(data=job_application)


@router.delete("/job_application/{job_application_id}", summary="删除投递记录", response_model=ResponseSchemaModel[int], dependencies=[DependsJwtAuth])
async def delete_job_application(
    job_application_id: int,
    db: CurrentSession,
    request: Request,
) -> ResponseSchemaModel[int]:
    deleted_count = await job_application_service.delete(db, job_application_id, request.user.id)
    return response_base.success(data=deleted_count)


@router.put(
    "/job_application/{job_application_id}", summary="更新投递记录", response_model=ResponseSchemaModel[JobApplicationSchema], dependencies=[DependsJwtAuth]
)
async def update_job_application(
    job_application_id: int,
    obj_in: UpdateJobApplication,
    db: CurrentSession,
    request: Request,
) -> ResponseSchemaModel[JobApplicationSchema]:
    updated_job_application = await job_application_service.update(
        db, obj_in, job_application_id, request.user.id
    )
    return response_base.success(data=updated_job_application)


@router.get(
    "/job_application/{job_application_id}", summary="获取投递记录详情", response_model=ResponseSchemaModel[JobApplicationSchema], dependencies=[DependsJwtAuth]
)
async def get_job_application_detail(
    job_application_id: int,
    db: CurrentSession,
    request: Request,
) -> ResponseSchemaModel[JobApplicationSchema]:
    job_application = await job_application_service.get(db, job_application_id, request.user.id)
    return response_base.success(data=job_application)


@router.get(
    "/job_application", summary="获取投递记录列表", response_model=ResponseSchemaModel[PageData[JobApplicationSchema]], dependencies=[DependsJwtAuth, DependsPagination]
)
async def get_job_application_list(
    db: CurrentSession,
    request: Request,
    page_params: _CustomPageParams = DependsPagination,
    job_posting_id: Optional[int] = Query(None, description="招聘信息 ID"),
    application_status: Optional[ApplicationStatus] = Query(None, description="投递状态"),
) -> ResponseSchemaModel[PageData[JobApplicationSchema]]:
    job_applications = await job_application_service.get_list(
        db, request.user.id, job_posting_id, application_status, page_params
    )
    return response_base.success(data=job_applications)
