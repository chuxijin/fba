#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.social.schema.metric import (
    CreateSocialWorkMetricParam,
    GetSocialWorkMetricDetail,
    SocialWorkTrendPoint,
    UpdateSocialWorkMetricParam,
)
from backend.app.social.service.metric_service import SocialWorkMetricService
from backend.common.pagination import DependsPagination, _CustomPageParams, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter(prefix='/social/metric', tags=['social:metric'])

service = SocialWorkMetricService()


@router.get('/{pk}', summary='获取作品数据详情', dependencies=[DependsJwtAuth])
async def get_social_work_metric(
    pk: Annotated[int, Path(description='数据 ID')],
) -> ResponseSchemaModel[GetSocialWorkMetricDetail]:
    data = await service.get(pk=pk)
    return response_base.success(data=GetSocialWorkMetricDetail.model_validate(data))


@router.get('', summary='分页获取作品数据列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_social_work_metric_list(
    db: CurrentSession,
    page_params: Annotated[_CustomPageParams, DependsPagination],
    work_id: Annotated[int | None, Query(description='作品ID')] = None,
) -> ResponseModel:
    stmt = await service.get_list(work_id=work_id)
    data = await paging_data(db, stmt)
    return response_base.success(data=data)


@router.post('', summary='创建作品数据快照', dependencies=[DependsJwtAuth])
async def create_social_work_metric(
    request: Request,
    db: CurrentSession,
    obj: CreateSocialWorkMetricParam,
) -> ResponseSchemaModel[GetSocialWorkMetricDetail]:
    current_user_id = getattr(request.state, 'user_id', None) or 0
    created = await service.create(obj=obj, current_user_id=current_user_id)
    return response_base.success(data=GetSocialWorkMetricDetail.model_validate(created))


@router.put('/{pk}', summary='更新作品数据快照', dependencies=[DependsJwtAuth])
async def update_social_work_metric(
    request: Request,
    pk: Annotated[int, Path(description='数据 ID')],
    obj: UpdateSocialWorkMetricParam,
) -> ResponseModel:
    current_user_id = getattr(request.state, 'user_id', None) or 0
    await service.update(pk=pk, obj=obj, current_user_id=current_user_id)
    return response_base.success()


@router.delete('', summary='删除作品数据快照', dependencies=[DependsJwtAuth])
async def delete_social_work_metric(
    pks: Annotated[list[int], Query(description='主键 ID 列表')],
) -> ResponseModel:
    await service.delete(pks=pks)
    return response_base.success()


@router.get('/trend/{work_id}', summary='获取作品多指标趋势', dependencies=[DependsJwtAuth])
async def get_social_work_trend(
    work_id: Annotated[int, Path(description='作品 ID')],
) -> ResponseSchemaModel[list[SocialWorkTrendPoint]]:
    """按时间升序返回各指标趋势"""
    from sqlalchemy import select

    from backend.app.social.model.metric import SocialWorkMetric
    from backend.database.db import async_db_session

    async with async_db_session() as db:
        stmt = (
            select(SocialWorkMetric)
            .where(SocialWorkMetric.work_id == work_id)
            .order_by(SocialWorkMetric.record_time.asc())
        )
        result = await db.execute(stmt)
        items = result.scalars().all()
        data = [
            SocialWorkTrendPoint(
                record_time=i.record_time,
                view_count=i.view_count,
                like_count=i.like_count,
                favorite_count=i.favorite_count,
                comment_count=i.comment_count,
                share_count=i.share_count,
            )
            for i in items
        ]
        return response_base.success(data=data)
