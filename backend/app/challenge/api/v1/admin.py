#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.challenge.schema.challenge import (
    CreateChallengeLevelParam,
    GetChallengeLevelDetail,
    UpdateChallengeLevelParam,
)
from backend.app.challenge.service.challenge_service import challenge_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/levels',
    summary='获取闯关关卡配置列表',
    dependencies=[Depends(RequestPermission('challenge:level:view')), DependsRBAC],
)
async def get_challenge_levels(
    db: CurrentSession,
    challenge_key: Annotated[str | None, Query(description='闯关标识')] = None,
    status: Annotated[str | None, Query(description='关卡状态')] = None,
) -> ResponseSchemaModel[list[GetChallengeLevelDetail]]:
    """
    获取闯关关卡配置列表

    :param db: 数据库会话
    :param challenge_key: 闯关标识
    :param status: 关卡状态
    :return:
    """
    data = await challenge_service.get_admin_levels(db=db, challenge_key=challenge_key, status=status)
    return response_base.success(data=data)


@router.get(
    '/levels/{level_id}',
    summary='获取闯关关卡配置详情',
    dependencies=[Depends(RequestPermission('challenge:level:view')), DependsRBAC],
)
async def get_challenge_level(
    db: CurrentSession,
    level_id: Annotated[int, Path(description='关卡 ID')],
) -> ResponseSchemaModel[GetChallengeLevelDetail]:
    """
    获取闯关关卡配置详情

    :param db: 数据库会话
    :param level_id: 关卡 ID
    :return:
    """
    data = await challenge_service.get_admin_level(db=db, level_id=level_id)
    return response_base.success(data=data)


@router.post(
    '/levels',
    summary='创建闯关关卡',
    dependencies=[Depends(RequestPermission('challenge:level:add')), DependsRBAC],
)
async def create_challenge_level(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateChallengeLevelParam,
) -> ResponseSchemaModel[GetChallengeLevelDetail]:
    """
    创建闯关关卡

    :param request: 请求对象
    :param db: 数据库会话
    :param obj: 创建参数
    :return:
    """
    data = await challenge_service.create_level(db=db, obj=obj, user_id=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/levels/{level_id}',
    summary='更新闯关关卡',
    dependencies=[Depends(RequestPermission('challenge:level:edit')), DependsRBAC],
)
async def update_challenge_level(
    request: Request,
    db: CurrentSessionTransaction,
    level_id: Annotated[int, Path(description='关卡 ID')],
    obj: UpdateChallengeLevelParam,
) -> ResponseSchemaModel[GetChallengeLevelDetail]:
    """
    更新闯关关卡

    :param request: 请求对象
    :param db: 数据库会话
    :param level_id: 关卡 ID
    :param obj: 更新参数
    :return:
    """
    data = await challenge_service.update_level(db=db, level_id=level_id, obj=obj, user_id=request.user.id)
    return response_base.success(data=data)


@router.post(
    '/levels/{level_id}/publish',
    summary='发布闯关关卡',
    dependencies=[Depends(RequestPermission('challenge:level:publish')), DependsRBAC],
)
async def publish_challenge_level(
    request: Request,
    db: CurrentSessionTransaction,
    level_id: Annotated[int, Path(description='关卡 ID')],
) -> ResponseSchemaModel[GetChallengeLevelDetail]:
    """
    发布闯关关卡

    :param request: 请求对象
    :param db: 数据库会话
    :param level_id: 关卡 ID
    :return:
    """
    data = await challenge_service.publish_level(db=db, level_id=level_id, user_id=request.user.id)
    return response_base.success(data=data)
