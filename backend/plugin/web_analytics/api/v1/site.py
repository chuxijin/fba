from typing import Annotated

from fastapi import APIRouter, Path

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.web_analytics.schema import CreateSiteParam, SiteDetail, UpdateSiteParam
from backend.plugin.web_analytics.service import analytics_service

router = APIRouter(dependencies=[DependsJwtAuth])


@router.post('', summary='创建统计站点')
async def create_site(
    db: CurrentSessionTransaction,
    obj: CreateSiteParam,
) -> ResponseSchemaModel[SiteDetail]:
    data = await analytics_service.create_site(db=db, obj=obj)
    return response_base.success(data=data)


@router.get('', summary='获取统计站点列表')
async def list_sites(db: CurrentSession) -> ResponseSchemaModel[list[SiteDetail]]:
    data = await analytics_service.list_sites(db=db)
    return response_base.success(data=data)


@router.get('/{site_id}', summary='获取统计站点详情')
async def get_site(
    db: CurrentSession,
    site_id: Annotated[int, Path(description='站点 ID')],
) -> ResponseSchemaModel[SiteDetail]:
    data = await analytics_service.get_site(db=db, site_id=site_id)
    return response_base.success(data=data)


@router.put('/{site_id}', summary='更新统计站点')
async def update_site(
    db: CurrentSessionTransaction,
    site_id: Annotated[int, Path(description='站点 ID')],
    obj: UpdateSiteParam,
) -> ResponseSchemaModel[SiteDetail]:
    data = await analytics_service.update_site(db=db, site_id=site_id, obj=obj)
    return response_base.success(data=data)


@router.post('/maintenance/run', summary='执行统计汇总与数据清理')
async def run_maintenance(db: CurrentSessionTransaction) -> ResponseSchemaModel[dict[str, int]]:
    data = await analytics_service.run_maintenance(db=db)
    return response_base.success(data=data)
