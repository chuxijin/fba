#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.admin.schema.feedback import (
    DeleteFeedbackParam,
    FeedbackQueryParam,
    GetFeedbackDetail,
    UpdateFeedbackParam,
)
from backend.app.admin.service.feedback_service import feedback_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '',
    summary='分页获取反馈列表',
    dependencies=[
        DependsJwtAuth,
        DependsPagination,
    ],
)
async def get_feedback_list(
    db: CurrentSession,
    feedback_type: Annotated[str | None, Query(description='反馈类型')] = None,
    status: Annotated[str | None, Query(description='处理状态')] = None,
    keyword: Annotated[str | None, Query(description='内容关键词')] = None,
    contact: Annotated[str | None, Query(description='联系方式')] = None,
    source_app: Annotated[str | None, Query(description='来源应用')] = None,
    source_platform: Annotated[str | None, Query(description='来源平台')] = None,
    target_type: Annotated[str | None, Query(description='关联目标类型')] = None,
    is_read: Annotated[bool | None, Query(description='是否已读')] = None,
) -> ResponseSchemaModel[PageData[GetFeedbackDetail]]:
    """
    获取反馈分页列表

    :param db: 数据库会话
    :param feedback_type: 反馈类型
    :param status: 处理状态
    :param keyword: 内容关键词
    :param contact: 联系方式
    :param source_app: 来源应用
    :param source_platform: 来源平台
    :param target_type: 关联目标类型
    :param is_read: 是否已读
    :return:
    """
    params = FeedbackQueryParam(
        feedback_type=feedback_type,
        status=status,
        keyword=keyword,
        contact=contact,
        source_app=source_app,
        source_platform=source_platform,
        target_type=target_type,
        is_read=is_read,
    )
    page_data = await feedback_service.get_list(db=db, params=params)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取反馈详情', dependencies=[DependsJwtAuth])
async def get_feedback_detail(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='反馈 ID')],
) -> ResponseSchemaModel[GetFeedbackDetail]:
    """
    获取反馈详情

    :param db: 数据库事务会话
    :param pk: 反馈 ID
    :return:
    """
    feedback = await feedback_service.get(db=db, pk=pk, mark_as_read=True)
    return response_base.success(data=feedback)


@router.put(
    '/{pk}',
    summary='更新反馈',
    dependencies=[DependsJwtAuth],
)
async def update_feedback(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='反馈 ID')],
    obj: UpdateFeedbackParam,
) -> ResponseModel:
    """
    更新反馈

    :param request: FastAPI 请求对象
    :param db: 数据库事务会话
    :param pk: 反馈 ID
    :param obj: 更新参数
    :return:
    """
    count = await feedback_service.update(db=db, pk=pk, obj=obj, handled_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='批量删除反馈',
    dependencies=[DependsJwtAuth],
)
async def delete_feedbacks(
    db: CurrentSessionTransaction,
    obj: DeleteFeedbackParam,
) -> ResponseModel:
    """
    批量删除反馈

    :param db: 数据库事务会话
    :param obj: 删除参数
    :return:
    """
    count = await feedback_service.delete_batch(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
