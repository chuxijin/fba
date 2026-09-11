from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.oc.schema.recruit_announcement import (
    CreateRecruitAnnouncementParam,
    GetRecruitAnnouncementWithCompanyDetail,
    UpdateRecruitAnnouncementParam,
)
from backend.plugin.oc.service.recruit_announcement_service import recruit_announcement_service

router = APIRouter()


@router.get('/stats', summary='获取公告统计数据', dependencies=[DependsJwtAuth])
async def get_announcement_stats(
    db: CurrentSession,
    recruitment_type: Annotated[str | None, Query(description='招聘类型（精确匹配）')] = None,
    job_category: Annotated[str | None, Query(description='岗位大类（campus=校招类 / intern=实习类）')] = None,
) -> ResponseModel:
    """获取公告统计数据"""
    data = await recruit_announcement_service.get_stats(
        db=db, recruitment_type=recruitment_type, job_category=job_category
    )
    return response_base.success(data=data)


@router.get('/{announcement_id}', summary='获取公告详情', dependencies=[DependsJwtAuth])
async def get_announcement(
    db: CurrentSession, announcement_id: Annotated[int, Path(description='公告 ID')]
) -> ResponseSchemaModel[GetRecruitAnnouncementWithCompanyDetail]:
    """获取公告详情（含公司信息）"""
    data = await recruit_announcement_service.get(db=db, announcement_id=announcement_id)
    return response_base.success(data=data)


@router.get('', summary='获取公告列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_announcement_list(
    db: CurrentSession,
    company_id: Annotated[int | None, Query(description='公司 ID')] = None,
    company_name: Annotated[str | None, Query(description='公司名称')] = None,
    recruitment_type: Annotated[str | None, Query(description='招聘类型（精确匹配）')] = None,
    recruit_target: Annotated[str | None, Query(description='招聘对象')] = None,
    location: Annotated[str | None, Query(description='工作地点')] = None,
    keyword: Annotated[str | None, Query(description='公告标题/岗位关键词')] = None,
    job_category: Annotated[str | None, Query(description='岗位大类（campus=校招类 / intern=实习类）')] = None,
) -> ResponseSchemaModel[PageData[GetRecruitAnnouncementWithCompanyDetail]]:
    """获取公告列表（含公司信息与网站列表）"""
    data = await recruit_announcement_service.get_list(
        db=db,
        company_id=company_id,
        company_name=company_name,
        recruitment_type=recruitment_type,
        recruit_target=recruit_target,
        location=location,
        keyword=keyword,
        job_category=job_category,
    )
    return response_base.success(data=data)


@router.post('', summary='创建公告', dependencies=[DependsJwtAuth])
async def create_announcement(
    db: CurrentSessionTransaction, obj: CreateRecruitAnnouncementParam
) -> ResponseModel:
    """创建招聘公告"""
    await recruit_announcement_service.create(db=db, obj=obj)
    return response_base.success()


@router.put('/{announcement_id}', summary='更新公告', dependencies=[DependsJwtAuth])
async def update_announcement(
    db: CurrentSessionTransaction,
    announcement_id: Annotated[int, Path(description='公告 ID')],
    obj: UpdateRecruitAnnouncementParam,
) -> ResponseModel:
    """更新招聘公告"""
    count = await recruit_announcement_service.update(db=db, announcement_id=announcement_id, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{announcement_id}', summary='删除公告', dependencies=[DependsJwtAuth])
async def delete_announcement(
    db: CurrentSessionTransaction, announcement_id: Annotated[int, Path(description='公告 ID')]
) -> ResponseModel:
    """删除招聘公告"""
    count = await recruit_announcement_service.delete(db=db, announcement_ids=[announcement_id])
    if count > 0:
        return response_base.success()
    return response_base.fail()
