from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request

from backend.app.job.schema.job_posting import (
    CreateJobPosting,
    GetJobPostingDetail,
    GetJobPostingListParams,
    JobPostingSchema,
    UpdateJobPosting,
)
from backend.app.job.service.job_posting_service import job_posting_service
from backend.database.db import CurrentSession
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.pagination import PageData, DependsPagination, _CustomPageParams
from backend.common.security.jwt import DependsJwtAuth, superuser_verify, get_current_user

router = APIRouter()


@router.post("/job_posting", summary="创建招聘信息", response_model=ResponseSchemaModel[JobPostingSchema], dependencies=[DependsJwtAuth, Depends(superuser_verify)])
async def create_job_posting(
    obj_in: CreateJobPosting,
    request: Request,
) -> ResponseSchemaModel[JobPostingSchema]:
    job_posting = await job_posting_service.create(request, obj_in, request.user.id)
    return await response_base.success(data=job_posting)


@router.delete("/job_posting/{job_posting_id}", summary="删除招聘信息", response_model=ResponseSchemaModel[int], dependencies=[DependsJwtAuth, Depends(superuser_verify)])
async def delete_job_posting(
    job_posting_id: int,
    request: Request,
) -> ResponseSchemaModel[int]:
    deleted_count = await job_posting_service.delete(request, job_posting_id)
    return await response_base.success(data=deleted_count)


@router.put("/job_posting/{job_posting_id}", summary="更新招聘信息", response_model=ResponseSchemaModel[JobPostingSchema], dependencies=[DependsJwtAuth, Depends(superuser_verify)])
async def update_job_posting(
    job_posting_id: int,
    obj_in: UpdateJobPosting,
    request: Request,
) -> ResponseSchemaModel[JobPostingSchema]:
    updated_job_posting = await job_posting_service.update(request, obj_in, job_posting_id, request.user.id)
    return await response_base.success(data=updated_job_posting)


@router.get("/job_posting/{job_posting_id}", summary="获取招聘信息详情", response_model=ResponseSchemaModel[JobPostingSchema], dependencies=[DependsJwtAuth])
async def get_job_posting_detail(
    job_posting_id: int,
    request: Request,
) -> ResponseSchemaModel[JobPostingSchema]:
    job_posting = await job_posting_service.get(request, job_posting_id)
    return await response_base.success(data=job_posting)


@router.get("/job_posting", summary="获取招聘信息列表", response_model=ResponseSchemaModel[PageData[JobPostingSchema]], dependencies=[DependsJwtAuth, DependsPagination])
async def get_job_posting_list(
    request: Request,
    page_params: _CustomPageParams = DependsPagination,
    company_name: Optional[str] = Query(None, description="公司名称"),
    position: Optional[str] = Query(None, description="岗位"),
    industry: Optional[str] = Query(None, description="所属行业"),
    recruitment_type: Optional[str] = Query(None, description="招聘类型"),
) -> ResponseSchemaModel[PageData[JobPostingSchema]]:
    job_postings = await job_posting_service.get_list(
        request, company_name, position, industry, recruitment_type, page_params
    )
    return await response_base.success(data=job_postings)
