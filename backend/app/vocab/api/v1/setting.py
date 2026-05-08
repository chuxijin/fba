#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request

from backend.app.vocab.schema.setting import GetSettingDetail, UpdateSettingParam
from backend.app.vocab.service.setting_service import setting_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter(prefix='/vocab/settings', tags=['学习设置'], dependencies=[DependsJwtAuth])


@router.get('', summary='获取学习设置')
async def get_setting(request: Request, db: CurrentSession) -> ResponseSchemaModel[GetSettingDetail]:
    """获取用户学习设置"""
    data = await setting_service.get_setting(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.put('', summary='更新学习设置')
async def update_setting(
    request: Request, db: CurrentSession, obj: UpdateSettingParam
) -> ResponseSchemaModel[GetSettingDetail]:
    """更新用户学习设置"""
    data = await setting_service.update_setting(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)
