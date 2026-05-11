#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.admin.schema.feedback import CreateFeedbackParam, GetMyFeedbackItem
from backend.app.admin.service.feedback_service import feedback_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.post('/feedbacks', summary='提交反馈')
async def create_feedback(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateFeedbackParam,
) -> ResponseModel:
    """
    提交反馈

    :param request: FastAPI 请求对象
    :param db: 数据库事务会话
    :param obj: 创建反馈参数
    :return:
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get('user-agent')
    user_id = request.user.id if getattr(request.user, 'is_authenticated', False) else None
    await feedback_service.create(
        db=db,
        obj=obj,
        ip_address=ip_address,
        user_agent=user_agent,
        user_id=user_id,
    )
    return response_base.success()


@router.get(
    '/feedbacks/mine',
    summary='获取我的反馈列表',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_my_feedbacks(
    request: Request,
    db: CurrentSession,
    feedback_type: Annotated[str | None, Query(description='反馈类型')] = None,
    status: Annotated[str | None, Query(description='处理状态')] = None,
) -> ResponseSchemaModel[PageData[GetMyFeedbackItem]]:
    """
    获取当前用户的反馈分页列表

    :param request: FastAPI 请求对象
    :param db: 数据库会话
    :param feedback_type: 反馈类型
    :param status: 处理状态
    :return:
    """
    page_data = await feedback_service.get_my_list(
        db=db,
        user_id=request.user.id,
        feedback_type=feedback_type,
        status=status,
    )
    return response_base.success(data=page_data)
