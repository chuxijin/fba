#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Request, Query, Path, Depends
from backend.app.gongkao.schema.feedback import (
    CreateFeedbackParam, 
    UpdateFeedbackParam, 
    DeleteFeedbackParam, 
    FeedbackParam, 
    GetFeedbackDetail
)
from backend.app.gongkao.service.feedback_service import feedback_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.database.db import CurrentSessionTransaction, CurrentSession
from backend.common.pagination import DependsPagination, PageData
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC

router = APIRouter()


@router.post('', summary='提交反馈')
async def create_feedback(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateFeedbackParam,
) -> ResponseModel:
    """提交反馈（公开接口）"""
    ip = request.client.host if request.client else None
    await feedback_service.create(db=db, obj=obj, ip_address=ip)
    return response_base.success()


@router.get(
    '', 
    summary='获取反馈列表',
    dependencies=[
        DependsPagination,
        Depends(RequestPermission('gongkao:feedback:list')), # 假设的权限
        DependsRBAC,
    ]
)
async def get_feedback_list(
    db: CurrentSession,
    type: Annotated[str | None, Query(description='反馈类型')] = None,
    status: Annotated[str | None, Query(description='处理状态')] = None,
    content: Annotated[str | None, Query(description='内容搜索')] = None,
    contact: Annotated[str | None, Query(description='联系人搜索')] = None,
    view_status: Annotated[int | None, Query(description='查看状态')] = None,
) -> ResponseSchemaModel[PageData[GetFeedbackDetail]]:
    """获取反馈列表（管理员）"""
    params = FeedbackParam(
        type=type,
        status=status,
        content=content,
        contact=contact,
        view_status=view_status,
    )
    data = await feedback_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.put(
    '/{pk}',
    summary='更新反馈状态/回复',
    dependencies=[
        Depends(RequestPermission('gongkao:feedback:update')),
        DependsRBAC,
    ],
)
async def update_feedback(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='反馈ID')],
    obj: UpdateFeedbackParam,
) -> ResponseModel:
    """更新反馈（管理员）"""
    count = await feedback_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除反馈',
    dependencies=[
        Depends(RequestPermission('gongkao:feedback:delete')),
        DependsRBAC,
    ],
)
async def delete_feedback(
    db: CurrentSessionTransaction,
    obj: DeleteFeedbackParam,
) -> ResponseModel:
    """删除反馈（管理员）"""
    await feedback_service.delete(db=db, obj=obj)
    return response_base.success()
