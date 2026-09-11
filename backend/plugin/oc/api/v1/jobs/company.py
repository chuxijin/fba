from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.oc.schema.company import (
    CreateCompanyParam,
    GetCompanyDetail,
    UpdateCompanyParam,
)
from backend.plugin.oc.service.company_service import oc_company_service

router = APIRouter()


@router.get('/{company_id}', summary='获取公司详情', dependencies=[DependsJwtAuth])
async def get_company(
    db: CurrentSession, company_id: Annotated[int, Path(description='公司 ID')]
) -> ResponseSchemaModel[GetCompanyDetail]:
    """获取公司详情（含网站列表）"""
    data = await oc_company_service.get(db=db, company_id=company_id)
    return response_base.success(data=data)


@router.get('', summary='获取公司列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_company_list(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='公司名称')] = None,
    company_type: Annotated[str | None, Query(description='公司类型')] = None,
    industry: Annotated[str | None, Query(description='所属行业')] = None,
    location: Annotated[str | None, Query(description='地点')] = None,
) -> ResponseSchemaModel[PageData[GetCompanyDetail]]:
    """获取公司列表"""
    data = await oc_company_service.get_list(
        db=db,
        name=name,
        company_type=company_type,
        industry=industry,
        location=location,
    )
    return response_base.success(data=data)


@router.post('', summary='创建公司', dependencies=[DependsJwtAuth])
async def create_company(db: CurrentSessionTransaction, obj: CreateCompanyParam) -> ResponseModel:
    """创建公司（含网站列表）"""
    await oc_company_service.create(db=db, obj=obj)
    return response_base.success()


@router.put('/{company_id}', summary='更新公司', dependencies=[DependsJwtAuth])
async def update_company(
    db: CurrentSessionTransaction,
    company_id: Annotated[int, Path(description='公司 ID')],
    obj: UpdateCompanyParam,
) -> ResponseModel:
    """更新公司（websites 传入时全量替换网站列表）"""
    count = await oc_company_service.update(db=db, company_id=company_id, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{company_id}', summary='删除公司', dependencies=[DependsJwtAuth])
async def delete_company(
    db: CurrentSessionTransaction, company_id: Annotated[int, Path(description='公司 ID')]
) -> ResponseModel:
    """删除公司（级联删除网站与公告）"""
    count = await oc_company_service.delete(db=db, company_ids=[company_id])
    if count > 0:
        return response_base.success()
    return response_base.fail()
