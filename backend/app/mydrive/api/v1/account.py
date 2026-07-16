#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.mydrive.schema.file import GetMyDriveFileList
from backend.app.mydrive.schema.account import CreateMyDriveAccountParam, GetMyDriveAccountDetail, UpdateMyDriveAccountParam
from backend.app.mydrive.service.account_service import mydrive_account_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('', summary='分页获取网盘账户', dependencies=[DependsJwtAuth, DependsPagination])
async def get_mydrive_accounts(
    request: Request,
    db: CurrentSession,
    provider: Annotated[str | None, Query(description='网盘驱动标识')] = None,
) -> ResponseSchemaModel[PageData[GetMyDriveAccountDetail]]:
    """分页获取当前用户的网盘账户。"""
    stmt = await mydrive_account_service.get_select(owner_id=request.user.id, provider=provider)
    return response_base.success(data=await paging_data(db, stmt))


@router.get('/{pk}', summary='获取网盘账户详情', dependencies=[DependsJwtAuth])
async def get_mydrive_account(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='账户 ID')],
) -> ResponseSchemaModel[GetMyDriveAccountDetail]:
    """获取当前用户的网盘账户详情。"""
    account = await mydrive_account_service.get(db, pk=pk, owner_id=request.user.id)
    return response_base.success(data=account)


@router.get('/{pk}/personal/list', summary='预览网盘账户个人空间目录', dependencies=[DependsJwtAuth])
async def get_mydrive_account_personal_files(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='账户 ID')],
    path: Annotated[str, Query(description='目录路径')] = '/',
    file_id: Annotated[str | None, Query(description='目录文件 ID')] = None,
    page: Annotated[int, Query(ge=1, description='页码')] = 1,
    per_page: Annotated[int, Query(ge=1, le=200, description='每页文件数')] = 200,
) -> ResponseSchemaModel[GetMyDriveFileList]:
    """预览当前用户网盘账户的个人空间目录。"""
    file_list = await mydrive_account_service.list_personal_files(
        db,
        pk=pk,
        owner_id=request.user.id,
        path=path,
        file_id=file_id,
        page=page,
        per_page=per_page,
    )
    return response_base.success(data=file_list)


@router.post('', summary='创建网盘账户', dependencies=[DependsJwtAuth])
async def create_mydrive_account(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateMyDriveAccountParam,
) -> ResponseSchemaModel[GetMyDriveAccountDetail]:
    """创建当前用户的网盘账户。"""
    account = await mydrive_account_service.create(db, owner_id=request.user.id, obj=obj)
    return response_base.success(data=account)


@router.put('/{pk}', summary='更新网盘账户', dependencies=[DependsJwtAuth])
async def update_mydrive_account(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='账户 ID')],
    obj: UpdateMyDriveAccountParam,
) -> ResponseModel:
    """更新当前用户的网盘账户。"""
    await mydrive_account_service.update(db, pk=pk, owner_id=request.user.id, obj=obj)
    return response_base.success()


@router.post('/{pk}/profile/sync', summary='同步网盘账户资料', dependencies=[DependsJwtAuth])
async def sync_mydrive_account_profile(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='账户 ID')],
) -> ResponseSchemaModel[GetMyDriveAccountDetail]:
    """同步当前用户的网盘账户资料。"""
    account = await mydrive_account_service.sync_profile(db, pk=pk, owner_id=request.user.id)
    return response_base.success(data=account)


@router.delete('/{pk}', summary='删除网盘账户', dependencies=[DependsJwtAuth])
async def delete_mydrive_account(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='账户 ID')],
) -> ResponseModel:
    """删除当前用户的网盘账户。"""
    await mydrive_account_service.delete(db, pk=pk, owner_id=request.user.id)
    return response_base.success()
