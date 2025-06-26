#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.plugin.app_auth.schema.statistics import AppAuthStatistics
from backend.plugin.app_auth.service.statistics_service import StatisticsService

router = APIRouter()

statistics_service = StatisticsService()


@router.get('/overview', summary='获取应用授权统计概览', dependencies=[DependsJwtAuth])
async def get_app_auth_statistics() -> ResponseModel:
    """
    获取应用授权统计概览
    
    :return: 统计数据
    """
    data = await statistics_service.get_app_auth_statistics()
    return response_base.success(data=data) 