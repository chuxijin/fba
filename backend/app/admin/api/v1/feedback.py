#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request

from backend.app.admin.schema.feedback import CreateFeedbackParam
from backend.app.admin.service.feedback_service import feedback_service
from backend.common.response.response_schema import ResponseModel, response_base
from backend.database.db import CurrentSessionTransaction

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
    await feedback_service.create(
        db=db,
        obj=obj,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return response_base.success()
