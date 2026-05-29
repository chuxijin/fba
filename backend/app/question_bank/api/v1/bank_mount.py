#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from backend.app.question_bank.schema.bank_mount import (
    CreateBankMountParam,
    DeleteBankMountParam,
    GetBankMountDetail,
    UpdateBankMountParam,
)
from backend.app.question_bank.service.bank_mount_service import bank_mount_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth, get_token, jwt_authentication
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


async def get_authenticated_user_id(request: Request) -> int:
    """
    获取认证用户 ID

    :param request: FastAPI 请求对象
    :return:
    """
    user_id = getattr(request.user, 'id', None)
    if user_id is not None:
        return int(user_id)

    token = get_token(request)
    user = await jwt_authentication(token)
    return int(user.id)


@router.get(
    '',
    summary='获取刷题内容挂载列表',
    name='qbank_get_bank_mount_list',
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
    ],
)
async def get_bank_mount_list(
    db: CurrentSession,
    collection_id: Annotated[int | None, Query(description='合集 ID')] = None,
    item_id: Annotated[int | None, Query(description='内容 ID')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[list[GetBankMountDetail]]:
    """🔐 管理员接口 - 获取刷题内容挂载列表"""
    data = await bank_mount_service.get_list(
        db=db,
        collection_id=collection_id,
        item_id=item_id,
        status=status,
    )
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建刷题内容挂载',
    name='qbank_create_bank_mount',
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
    ],
)
async def create_bank_mount(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateBankMountParam,
) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以创建刷题内容挂载"""
    user_id = await get_authenticated_user_id(request)
    await bank_mount_service.create(db=db, obj=obj, created_by=user_id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新刷题内容挂载',
    name='qbank_update_bank_mount',
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
    ],
)
async def update_bank_mount(
    request: Request,
    db: CurrentSessionTransaction,
    pk: int,
    obj: UpdateBankMountParam,
) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以更新刷题内容挂载"""
    user_id = await get_authenticated_user_id(request)
    count = await bank_mount_service.update(db=db, pk=pk, obj=obj, updated_by=user_id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除刷题内容挂载',
    name='qbank_delete_bank_mount',
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
    ],
)
async def delete_bank_mount(db: CurrentSessionTransaction, obj: DeleteBankMountParam) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以删除刷题内容挂载"""
    count = await bank_mount_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
