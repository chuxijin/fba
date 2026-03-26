#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.trail.schema.point import BatchCreateTrailPointParam, GetTrailPointDetail
from backend.app.trail.service.trail_point_service import trail_point_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.post(
    '/batch',
    summary='批量上传轨迹点',
    dependencies=[DependsJwtAuth],
)
async def batch_upload(
    request: Request,
    obj: BatchCreateTrailPointParam,
    db: CurrentSessionTransaction,
) -> ResponseModel:
    count = await trail_point_service.batch_upload(db, request.user.id, obj)
    return response_base.success(data={'count': count})


@router.get(
    '',
    summary='查询轨迹点',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_trail_points(
    request: Request,
    db: CurrentSession,
    start_time: Annotated[datetime, Query(description='开始时间')],
    end_time: Annotated[datetime, Query(description='结束时间')],
) -> ResponseSchemaModel[PageData[GetTrailPointDetail]]:
    data = await trail_point_service.get_trail_points(
        db=db,
        user_id=request.user.id,
        start_time=start_time,
        end_time=end_time,
    )
    return response_base.success(data=data)


@router.get(
    '/latest',
    summary='获取最新位置',
    dependencies=[DependsJwtAuth],
)
async def get_latest_point(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[GetTrailPointDetail | None]:
    point = await trail_point_service.get_latest(db, request.user.id)
    return response_base.success(data=point)
