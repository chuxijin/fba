#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.invite.schema.invite import AcceptInviteParam, AcceptInviteResult
from backend.app.invite.service.invite_service import invite_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/invite/relations', tags=['邀请关系'])


@router.post('/accept', summary='接受邀请', dependencies=[DependsJwtAuth])
async def accept_invite(
    request: Request,
    db: CurrentSessionTransaction,
    obj: AcceptInviteParam,
) -> ResponseSchemaModel[AcceptInviteResult]:
    """当前登录用户填写邀请码，建立邀请关系并发放奖励"""
    data = await invite_service.accept_invite(db=db, invitee_user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get('', summary='获取邀请记录', dependencies=[DependsJwtAuth, DependsPagination])
async def get_invite_relations_paginated(
    db: CurrentSession,
    inviter_user_id: Annotated[int | None, Query(description='邀请人用户 ID')] = None,
    invitee_user_id: Annotated[int | None, Query(description='被邀请人用户 ID')] = None,
) -> ResponseModel:
    """查看邀请关系列表"""
    data = await invite_service.get_invite_list(
        db=db,
        inviter_user_id=inviter_user_id,
        invitee_user_id=invitee_user_id,
    )
    return response_base.success(data=data)


@router.get('/stats', summary='获取邀请统计', dependencies=[DependsJwtAuth])
async def get_invite_stats(
    request: Request,
    db: CurrentSession,
) -> ResponseModel:
    """获取当前登录用户的邀请统计"""
    data = await invite_service.get_invite_stats(db=db, user_id=request.user.id)
    return response_base.success(data=data)
