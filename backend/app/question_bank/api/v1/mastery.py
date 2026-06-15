#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request

from backend.app.question_bank.schema.mastery import (
    GetForgottenItem,
    GetMasteryStatsResponse,
)
from backend.app.question_bank.service.mastery_service import mastery_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get(
    '/stats',
    summary='获取掌握状态统计',
    name='qbank_mastery_stats',
    dependencies=[DependsJwtAuth],
)
async def get_mastery_stats(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[GetMasteryStatsResponse]:
    """获取用户掌握状态统计（未掌握/已掌握/遗忘）"""
    data = await mastery_service.get_stats(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.get(
    '/forgotten',
    summary='获取遗忘题目列表',
    name='qbank_mastery_forgotten',
    dependencies=[DependsJwtAuth],
)
async def get_forgotten_list(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetForgottenItem]]:
    """获取遗忘题目列表（需要复习的题目）"""
    data = await mastery_service.get_forgotten_list(db=db, user_id=request.user.id)
    return response_base.success(data=data)
