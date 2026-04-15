#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Request

from backend.app.question_bank.schema.knowledge_point import GetKpDetailResponse, GetKpProgressResponse
from backend.app.question_bank.service.knowledge_point_service import knowledge_point_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('/{pk}', summary='获取知识点分类详情', name='qbank_get_kp_detail')
async def get_kp_detail(
    db: CurrentSession,
    pk: Annotated[int, Path(description='分类 ID')],
) -> ResponseSchemaModel[GetKpDetailResponse]:
    """🌍 公开接口 - 获取知识点分类详情（含子知识点树和题量统计）"""
    data = await knowledge_point_service.get_detail(db=db, category_id=pk)
    return response_base.success(data=data)


@router.get(
    '/{pk}/progress',
    summary='获取知识点做题进度',
    name='qbank_get_kp_progress',
    dependencies=[DependsJwtAuth],
)
async def get_kp_progress(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='分类 ID')],
) -> ResponseSchemaModel[GetKpProgressResponse]:
    """🔒 登录接口 - 获取用户在指定知识点下的做题进度"""
    data = await knowledge_point_service.get_progress(db=db, category_id=pk, user_id=request.user.id)
    return response_base.success(data=data)
