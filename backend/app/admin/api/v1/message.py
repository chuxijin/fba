#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.admin.schema.message import GetMyMessageItem
from backend.app.admin.service.message_service import message_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/messages/mine',
    summary='获取我的消息列表',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_my_sys_messages(
    request: Request,
    db: CurrentSession,
    unread_only: Annotated[bool, Query(description='是否只看未读')] = False,
    message_type: Annotated[str | None, Query(description='消息类型')] = None,
) -> ResponseSchemaModel[PageData[GetMyMessageItem]]:
    """
    获取当前用户的消息分页列表

    :param request: FastAPI 请求对象
    :param db: 数据库会话
    :param unread_only: 是否只看未读
    :param message_type: 消息类型
    :return:
    """
    page_data = await message_service.get_my_list(
        db=db,
        user_id=request.user.id,
        unread_only=unread_only,
        message_type=message_type,
    )
    return response_base.success(data=page_data)


@router.get(
    '/messages/unread-count',
    summary='获取未读消息数',
    dependencies=[DependsJwtAuth],
)
async def get_sys_message_unread_count(
    request: Request,
    db: CurrentSession,
) -> ResponseModel:
    """
    获取当前用户的未读消息数

    :param request: FastAPI 请求对象
    :param db: 数据库会话
    :return:
    """
    count = await message_service.count_unread(db=db, user_id=request.user.id)
    return response_base.success(data={'count': count})


@router.put(
    '/messages/read-all',
    summary='标记全部消息已读',
    dependencies=[DependsJwtAuth],
)
async def mark_all_sys_messages_read(
    request: Request,
    db: CurrentSessionTransaction,
) -> ResponseModel:
    """
    标记当前用户全部消息已读

    :param request: FastAPI 请求对象
    :param db: 数据库事务会话
    :return:
    """
    count = await message_service.mark_all_read(db=db, user_id=request.user.id)
    return response_base.success(data={'count': count})


@router.get(
    '/messages/{pk}',
    summary='获取我的消息详情',
    dependencies=[DependsJwtAuth],
)
async def get_my_sys_message_detail(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='消息 ID')],
) -> ResponseSchemaModel[GetMyMessageItem]:
    """
    获取当前用户的消息详情

    :param request: FastAPI 请求对象
    :param db: 数据库会话
    :param pk: 消息 ID
    :return:
    """
    detail = await message_service.get_my_detail(db=db, pk=pk, user_id=request.user.id)
    return response_base.success(data=detail)


@router.put(
    '/messages/{pk}/read',
    summary='标记消息已读',
    dependencies=[DependsJwtAuth],
)
async def mark_sys_message_read(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='消息 ID')],
) -> ResponseModel:
    """
    标记单条消息已读

    :param request: FastAPI 请求对象
    :param db: 数据库事务会话
    :param pk: 消息 ID
    :return:
    """
    await message_service.mark_read(db=db, pk=pk, user_id=request.user.id)
    return response_base.success()
