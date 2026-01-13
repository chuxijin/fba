#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.question_bank.schema.notice import (
    CreateNoticeParam,
    GetActiveNotice,
    GetNoticeDetail,
    UpdateNoticeParam,
)
from backend.app.question_bank.service.notice_service import NoticeService
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()

notice_service = NoticeService()


@router.get('', summary='获取启用的通知列表', name='qbank_get_active_notices')
async def get_active_notices(
    db: CurrentSession,
    scene: Annotated[str | None, Query(description='展示场景筛选')] = None,
) -> ResponseSchemaModel[list[GetActiveNotice]]:
    """🌍 公开接口 - 获取启用且在有效期内的通知"""
    data = await notice_service.get_active_list(db=db, scene=scene)
    return response_base.success(data=data)


@router.get(
    '/admin',
    summary='获取通知列表（管理）',
    name='qbank_admin_get_notices',
    dependencies=[
        Depends(RequestPermission('question_bank:notice:read')),
        DependsRBAC,
    ],
)
async def get_notices(
    db: CurrentSession,
    status: Annotated[int | None, Query(description='状态筛选')] = None,
    notice_type: Annotated[str | None, Query(description='通知类型筛选')] = None,
    scene: Annotated[str | None, Query(description='展示场景筛选')] = None,
) -> ResponseSchemaModel[list[GetNoticeDetail]]:
    """🔐 管理员接口 - 获取通知列表"""
    data = await notice_service.get_list(db=db, status=status, notice_type=notice_type, scene=scene)
    return response_base.success(data=data)


@router.get(
    '/{pk}',
    summary='获取通知详情（管理）',
    name='qbank_admin_get_notice',
    dependencies=[
        Depends(RequestPermission('question_bank:notice:read')),
        DependsRBAC,
    ],
)
async def get_notice(
    db: CurrentSession,
    pk: Annotated[int, Path(description='通知 ID')],
) -> ResponseSchemaModel[GetNoticeDetail]:
    """🔐 管理员接口 - 获取通知详情"""
    data = await notice_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建通知',
    name='qbank_admin_create_notice',
    dependencies=[
        Depends(RequestPermission('question_bank:notice:create')),
        DependsRBAC,
    ],
)
async def create_notice(db: CurrentSessionTransaction, obj: CreateNoticeParam) -> ResponseModel:
    """🔐 管理员接口 - 创建通知"""
    await notice_service.create(db=db, obj_in=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新通知',
    name='qbank_admin_update_notice',
    dependencies=[
        Depends(RequestPermission('question_bank:notice:update')),
        DependsRBAC,
    ],
)
async def update_notice(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='通知 ID')],
    obj: UpdateNoticeParam,
) -> ResponseModel:
    """🔐 管理员接口 - 更新通知"""
    await notice_service.update(db=db, pk=pk, obj_in=obj)
    return response_base.success()


@router.delete(
    '/{pk}',
    summary='删除通知',
    name='qbank_admin_delete_notice',
    dependencies=[
        Depends(RequestPermission('question_bank:notice:delete')),
        DependsRBAC,
    ],
)
async def delete_notice(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='通知 ID')],
) -> ResponseModel:
    """🔐 管理员接口 - 删除通知"""
    await notice_service.delete(db=db, pk=pk)
    return response_base.success()
