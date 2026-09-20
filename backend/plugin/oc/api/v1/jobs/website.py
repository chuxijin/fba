from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.oc.schema.company import (
    CreateWebsiteParam,
    GetWebsiteListDetail,
    UpdateWebsiteParam,
)
from backend.plugin.oc.service.company_service import oc_company_service

router = APIRouter()


@router.get('', summary='获取网站列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_website_list(
    db: CurrentSession,
    company_name: Annotated[str | None, Query(description='公司名称（模糊）')] = None,
    name: Annotated[str | None, Query(description='网站名称（模糊）')] = None,
    url: Annotated[str | None, Query(description='网站链接（模糊）')] = None,
) -> ResponseSchemaModel[PageData[GetWebsiteListDetail]]:
    """获取网站列表（含所属公司名称）"""
    data = await oc_company_service.get_website_list(
        db=db,
        company_name=company_name,
        name=name,
        url=url,
    )
    return response_base.success(data=data)


@router.post('', summary='创建网站', dependencies=[DependsJwtAuth])
async def create_website(db: CurrentSessionTransaction, obj: CreateWebsiteParam) -> ResponseModel:
    """创建公司网站"""
    await oc_company_service.create_website(db=db, obj=obj)
    return response_base.success()


@router.put('/{website_id}', summary='更新网站', dependencies=[DependsJwtAuth])
async def update_website(
    db: CurrentSessionTransaction,
    website_id: Annotated[int, Path(description='网站 ID')],
    obj: UpdateWebsiteParam,
) -> ResponseModel:
    """更新公司网站"""
    count = await oc_company_service.update_website(db=db, website_id=website_id, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{website_id}', summary='删除网站', dependencies=[DependsJwtAuth])
async def delete_website(
    db: CurrentSessionTransaction, website_id: Annotated[int, Path(description='网站 ID')]
) -> ResponseModel:
    """删除公司网站"""
    count = await oc_company_service.delete_website(db=db, website_ids=[website_id])
    if count > 0:
        return response_base.success()
    return response_base.fail()
