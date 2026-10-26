#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.cms.service.share_service import share_service
from backend.app.invite.schema.invite import CreateInviteCodeParam, GetInviteCodeDetail
from backend.app.invite.service.invite_service import invite_service
from backend.common.exception import errors
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.utils.wechat_code import create_miniapp_code

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


@router.get('/mine/qrcode', summary='生成本人的邀请小程序码', dependencies=[DependsJwtAuth])
async def get_my_invite_qrcode(request: Request, db: CurrentSession) -> ResponseModel:
    code = await invite_service.get_my_code(db=db, user_id=request.user.id, campaign_id=None)
    if code.status != 1 or (code.max_uses > 0 and code.used_count >= code.max_uses):
        raise errors.RequestError(msg='当前邀请码不可用')
    image = await create_miniapp_code(page='pages/practice/index', scene=f'iv_{code.code}')
    return response_base.success(data={'code': code.code, 'data_url': image})


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
    return response_base.success(data=await share_service.legacy_invite_config(db))
