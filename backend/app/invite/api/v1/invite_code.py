#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.invite.schema.invite import (
    AcceptInviteParam,
    AcceptInviteResult,
    CreateInviteCodeParam,
    GetInviteCodeDetail,
    GetInviteRelationDetail,
)
from backend.app.invite.service.invite_service import invite_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/invite/codes', tags=['邀请码'])


@router.get('/mine', summary='获取我的邀请码', dependencies=[DependsJwtAuth])
async def get_my_invite_code(
    db: CurrentSession,
    user_id: Annotated[int, Query(description='用户 ID')],
    campaign_id: Annotated[int | None, Query(description='活动 ID')] = None,
) -> ResponseSchemaModel[GetInviteCodeDetail]:
    """获取当前用户的邀请码，不存在则自动创建"""
    data = await invite_service.get_my_code(db=db, user_id=user_id, campaign_id=campaign_id)
    return response_base.success(data=data)


@router.post('', summary='创建邀请码', dependencies=[DependsJwtAuth])
async def create_invite_code(
    db: CurrentSessionTransaction,
    user_id: Annotated[int, Query(description='用户 ID')],
    obj: CreateInviteCodeParam,
) -> ResponseSchemaModel[GetInviteCodeDetail]:
    """为指定活动创建新的邀请码"""
    data = await invite_service.create_code(db=db, user_id=user_id, obj=obj)
    return response_base.success(data=data)


@router.get('', summary='获取邀请码列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_invite_codes_paginated(
    db: CurrentSession,
    user_id: Annotated[int | None, Query(description='用户 ID')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
    campaign_id: Annotated[int | None, Query(description='活动 ID')] = None,
) -> ResponseModel:
    """管理端：查看邀请码列表"""
    data = await invite_service.get_code_list(db=db, user_id=user_id, status=status, campaign_id=campaign_id)
    return response_base.success(data=data)
