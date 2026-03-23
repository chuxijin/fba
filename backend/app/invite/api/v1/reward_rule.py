#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.invite.schema.invite import CreateRewardRuleParam, GetRewardRuleDetail, UpdateRewardRuleParam
from backend.app.invite.service.invite_service import invite_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/invite/reward-rules', tags=['邀请奖励规则'])


@router.post('', summary='创建奖励规则', dependencies=[DependsJwtAuth])
async def create_reward_rule(
    db: CurrentSessionTransaction,
    obj: CreateRewardRuleParam,
) -> ResponseSchemaModel[GetRewardRuleDetail]:
    """管理端：创建邀请奖励规则"""
    data = await invite_service.create_reward_rule(db=db, obj=obj)
    return response_base.success(data=data)


@router.put('/{pk}', summary='更新奖励规则', dependencies=[DependsJwtAuth])
async def update_reward_rule(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='规则 ID')],
    obj: UpdateRewardRuleParam,
) -> ResponseModel:
    """管理端：更新邀请奖励规则"""
    await invite_service.update_reward_rule(db=db, pk=pk, obj=obj)
    return response_base.success()


@router.get('/{pk}', summary='获取奖励规则详情', dependencies=[DependsJwtAuth])
async def get_reward_rule(
    db: CurrentSession,
    pk: Annotated[int, Path(description='规则 ID')],
) -> ResponseSchemaModel[GetRewardRuleDetail]:
    """获取奖励规则详情"""
    data = await invite_service.get_reward_rule(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取奖励规则列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_reward_rules_paginated(
    db: CurrentSession,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseModel:
    """管理端：查看奖励规则列表"""
    data = await invite_service.get_reward_rule_list(db=db, status=status)
    return response_base.success(data=data)
