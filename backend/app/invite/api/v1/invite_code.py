#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.invite.schema.invite import CreateInviteCodeParam, GetInviteCodeDetail
from backend.app.invite.service.invite_service import invite_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
import json

from backend.plugin.config.crud.crud_config import config_dao
from backend.plugin.config.enums import ConfigType

router = APIRouter(prefix='/invite/codes', tags=['邀请码'])


@router.get('/mine', summary='获取我的邀请码', dependencies=[DependsJwtAuth])
async def get_my_invite_code(
    request: Request,
    db: CurrentSession,
    campaign_id: Annotated[int | None, Query(description='活动 ID')] = None,
) -> ResponseSchemaModel[GetInviteCodeDetail]:
    """获取当前用户的邀请码，不存在则自动创建"""
    data = await invite_service.get_my_code(db=db, user_id=request.user.id, campaign_id=campaign_id)
    return response_base.success(data=data)


@router.post('', summary='创建邀请码', dependencies=[DependsJwtAuth])
async def create_invite_code(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateInviteCodeParam,
) -> ResponseSchemaModel[GetInviteCodeDetail]:
    """为当前用户创建邀请码"""
    data = await invite_service.create_code(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get('', summary='获取邀请码列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_invite_codes_paginated(
    db: CurrentSession,
    user_id: Annotated[int | None, Query(description='用户 ID')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
    campaign_id: Annotated[int | None, Query(description='活动 ID')] = None,
) -> ResponseModel:
    data = await invite_service.get_code_list(db=db, user_id=user_id, status=status, campaign_id=campaign_id)
    return response_base.success(data=data)


@router.get('/share-config', summary='获取分享有礼配置')
async def get_invite_share_config(db: CurrentSession) -> ResponseSchemaModel[list[dict[str, str]]]:
    """
    获取分享有礼配置列表

    :param db: 数据库会话
    :return:
    """
    configs = await config_dao.get_all(db, type=ConfigType.invite)
    result = []
    for item in configs:
        if not item.is_frontend:
            continue
        try:
            val = json.loads(item.value)
            result.append({
                'title': val.get('title', ''),
                'image': val.get('image', ''),
            })
        except Exception:
            # 兼容非 JSON 格式
            result.append({
                'title': item.value,
                'image': '',
            })

    if not result:
        result.append({
            'title': '送你一份 VIP 学习订阅',
            'image': '',
        })

    return response_base.success(data=result)
