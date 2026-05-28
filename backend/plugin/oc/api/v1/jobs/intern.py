from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.plugin.oc.schema.intern_recruit import (
    CreateInternRecruitParam,
    GetInternRecruitDetail,
    UpdateInternRecruitParam,
)
from backend.plugin.oc.service.intern_recruit_service import intern_recruit_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{job_id}', summary='获取实习岗位详情', dependencies=[DependsJwtAuth])
async def get_intern_recruit(
    db: CurrentSession, job_id: Annotated[int, Path(description='岗位 ID')]
) -> ResponseSchemaModel[GetInternRecruitDetail]:
    """获取实习岗位详情"""
    data = await intern_recruit_service.get(db=db, job_id=job_id)
    return response_base.success(data=data)


@router.get('', summary='获取实习岗位列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_intern_recruit_list(
    db: CurrentSession,
    company_name: Annotated[str | None, Query(description='公司名称')] = None,
    company_type: Annotated[str | None, Query(description='公司类型')] = None,
    industry: Annotated[str | None, Query(description='所属行业')] = None,
    recruitment_type: Annotated[str | None, Query(description='招聘类型')] = None,
    recruit_target: Annotated[str | None, Query(description='招聘对象')] = None,
    location: Annotated[str | None, Query(description='工作地点')] = None,
    position: Annotated[str | None, Query(description='岗位')] = None,
    application_status: Annotated[str | None, Query(description='投递进度')] = None,
) -> ResponseSchemaModel[PageData[GetInternRecruitDetail]]:
    """获取实习岗位列表"""
    data = await intern_recruit_service.get_list(
        db=db,
        company_name=company_name,
        company_type=company_type,
        industry=industry,
        recruitment_type=recruitment_type,
        recruit_target=recruit_target,
        location=location,
        position=position,
        application_status=application_status,
    )
    return response_base.success(data=data)


@router.post('', summary='创建实习岗位', dependencies=[DependsJwtAuth])
async def create_intern_recruit(
    db: CurrentSessionTransaction, obj: CreateInternRecruitParam
) -> ResponseModel:
    """创建实习岗位"""
    await intern_recruit_service.create(db=db, obj=obj)
    return response_base.success()


@router.put('/{job_id}', summary='更新实习岗位', dependencies=[DependsJwtAuth])
async def update_intern_recruit(
    db: CurrentSessionTransaction,
    job_id: Annotated[int, Path(description='岗位 ID')],
    obj: UpdateInternRecruitParam,
) -> ResponseModel:
    """更新实习岗位"""
    count = await intern_recruit_service.update(db=db, job_id=job_id, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{job_id}', summary='删除实习岗位', dependencies=[DependsJwtAuth])
async def delete_intern_recruit(
    db: CurrentSessionTransaction, job_id: Annotated[int, Path(description='岗位 ID')]
) -> ResponseModel:
    """删除实习岗位"""
    count = await intern_recruit_service.delete(db=db, job_ids=[job_id])
    if count > 0:
        return response_base.success()
    return response_base.fail()
