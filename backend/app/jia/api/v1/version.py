#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query

from backend.app.jia.schema.app_version import CreateAppVersionParam, GetAppVersionDetail
from backend.app.jia.service.app_version_service import app_version_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/latest', summary='获取最新版本')
async def get_latest_version(
    db: CurrentSession,
    platform: Annotated[str, Query(description='平台(android/ios)')] = 'android',
) -> ResponseSchemaModel[GetAppVersionDetail]:
    """获取指定平台的最新版本信息"""
    data = await app_version_service.get_latest(db=db, platform=platform)
    return response_base.success(data=data)


@router.post('', summary='发布新版本')
async def create_app_version(
    db: CurrentSessionTransaction,
    obj: CreateAppVersionParam,
    platform: Annotated[str, Query(description='平台(android/ios)')] = 'android',
) -> ResponseSchemaModel[GetAppVersionDetail]:
    """发布新版本"""
    data = await app_version_service.create_version(db=db, platform=platform, obj=obj)
    return response_base.success(data=data)
