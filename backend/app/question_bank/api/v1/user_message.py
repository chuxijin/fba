#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.question_bank.schema.user_message import (
    CreateUserMessageParam,
    GetUserMessageDetail,
    GetUserMessageListItem,
    UpdateUserMessageParam,
    UserMessageUnreadCount,
)
from backend.app.question_bank.service.user_message_service import user_message_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('', summary='获取我的消息列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_my_messages(
    request: Request,
    db: CurrentSession,
    unread_only: Annotated[bool, Query(description='是否只看未读')] = False,
    message_type: Annotated[str | None, Query(description='消息类型')] = None,
) -> ResponseSchemaModel[PageData[GetUserMessageListItem]]:
    """获取我的消息列表"""
    data = await user_message_service.get_user_list(
        db=db,
        user_id=request.user.id,
        unread_only=unread_only,
        message_type=message_type,
    )
    return response_base.success(data=data)


@router.get('/unread-count', summary='获取我的未读消息数', dependencies=[DependsJwtAuth])
async def get_my_unread_count(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[UserMessageUnreadCount]:
    """获取我的未读消息数"""
    count = await user_message_service.count_unread(db=db, user_id=request.user.id)
    return response_base.success(data=UserMessageUnreadCount(count=count))


@router.get(
    '/admin',
    summary='获取消息列表（管理）',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_messages_admin(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='标题关键词')] = None,
    message_type: Annotated[str | None, Query(description='消息类型')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetUserMessageListItem]]:
    """获取消息列表（管理端）"""
    data = await user_message_service.get_admin_list(
        db=db,
        title=title,
        message_type=message_type,
        status=status,
    )
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取我的消息详情', dependencies=[DependsJwtAuth])
async def get_my_message(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='消息 ID')],
) -> ResponseSchemaModel[GetUserMessageDetail]:
    """获取我的消息详情"""
    data = await user_message_service.get_user_detail(db=db, message_id=pk, user_id=request.user.id)
    return response_base.success(data=data)


@router.put('/{pk}/read', summary='标记消息已读', dependencies=[DependsJwtAuth])
async def mark_message_read(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='消息 ID')],
) -> ResponseModel:
    """标记消息已读"""
    await user_message_service.mark_read(db=db, message_id=pk, user_id=request.user.id)
    return response_base.success()


@router.put('/read-all', summary='标记全部消息已读', dependencies=[DependsJwtAuth])
async def mark_all_messages_read(
    request: Request,
    db: CurrentSessionTransaction,
) -> ResponseModel:
    """标记全部消息已读"""
    await user_message_service.mark_all_read(db=db, user_id=request.user.id)
    return response_base.success()


@router.post(
    '/admin',
    summary='创建消息（管理）',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:message:create')), DependsRBAC],
)
async def create_message_admin(db: CurrentSessionTransaction, obj: CreateUserMessageParam) -> ResponseModel:
    """创建消息"""
    await user_message_service.create(db=db, obj_in=obj)
    return response_base.success()


@router.put(
    '/admin/{pk}',
    summary='更新消息（管理）',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:message:update')), DependsRBAC],
)
async def update_message_admin(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='消息 ID')],
    obj: UpdateUserMessageParam,
) -> ResponseModel:
    """更新消息"""
    count = await user_message_service.update(db=db, pk=pk, obj_in=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/admin/{pk}',
    summary='删除消息（管理）',
    dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:message:delete')), DependsRBAC],
)
async def delete_message_admin(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='消息 ID')],
) -> ResponseModel:
    """删除消息"""
    count = await user_message_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
