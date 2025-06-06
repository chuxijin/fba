#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.service.filesync_service import file_sync_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.post(
    '/execute/{config_id}',
    summary='执行同步任务',
    description='根据配置ID执行同步任务',
    response_model=ResponseSchemaModel[dict],
    dependencies=[DependsJwtAuth]
)
async def execute_sync_task(
    config_id: Annotated[int, Path(description="同步配置ID")],
    db: CurrentSession
) -> ResponseSchemaModel[dict]:
    """执行同步任务"""
    result = await file_sync_service.execute_sync_by_config_id(config_id, db)
    
    # 确保 result 不为 None
    if not result:
        return response_base.fail(res=ResponseModel(code=500, msg="同步任务执行失败，返回结果为空"))
    
    if not result.get("success", False):
        error_msg = result.get("error", "未知错误")
        return response_base.fail(res=ResponseModel(code=400, msg=error_msg))
    
    return response_base.success(data=result)
