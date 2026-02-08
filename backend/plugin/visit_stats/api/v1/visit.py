#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Request, Query

from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.visit_stats.schema import VisitStatsResponse
from backend.plugin.visit_stats.service import visit_service

router = APIRouter()


@router.post('/record', summary='记录访问')
async def record_visit(
    request: Request,
    db: CurrentSessionTransaction,
    path: Annotated[str | None, Query(description='访问路径')] = None,
) -> ResponseModel:
    """
    记录一次页面访问（公开接口，用于前端埋点）
    """
    ip = request.client.host if request.client else '0.0.0.0'
    user_agent = request.headers.get('user-agent')
    referer = request.headers.get('referer')

    await visit_service.record_visit(
        db=db,
        ip_address=ip,
        user_agent=user_agent,
        referer=referer,
        path=path,
    )
    return response_base.success()


@router.get('/stats', summary='获取访问统计')
async def get_visit_stats(
    db: CurrentSession,
) -> ResponseSchemaModel[VisitStatsResponse]:
    """
    获取网站访问统计数据（公开接口）
    """
    stats = await visit_service.get_stats(db=db)
    return response_base.success(data=stats)
