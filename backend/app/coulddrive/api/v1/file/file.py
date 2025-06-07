#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from backend.app.coulddrive.schema.file import (
    BaseFileInfo, 
    ListFilesParam, 
    ListShareFilesParam,
    MkdirParam,
    RemoveParam,
    TransferParam
)
from backend.app.coulddrive.service.yp_service import get_drive_manager
from backend.common.pagination import DependsPagination, PageData, paging_list_data, _CustomPageParams
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get(
    '/list',
    summary='获取文件列表',
    description='获取网盘文件列表，支持缓存加速',
    response_model=ResponseSchemaModel[PageData[BaseFileInfo]],
    dependencies=[DependsJwtAuth, DependsPagination]
)
async def get_file_list(
    db: CurrentSession,
    request: Request,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: Annotated[ListFilesParam, Depends()],
    page_params: Annotated[_CustomPageParams, DependsPagination]
) -> ResponseSchemaModel[PageData[BaseFileInfo]]:
    """获取文件列表，支持智能缓存"""
    drive_manager = get_drive_manager()
    
    # 从x-token(cookies)获取网盘账户ID
    drive_account_id = None
    try:
        from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
        # x-token就是cookies，直接通过cookies获取对应的网盘账户ID
        drive_account_id = await drive_account_dao.get_id_by_cookies(db, x_token)
    except Exception as e:
        # 如果获取账户ID失败，不影响正常功能，只是不使用缓存
        pass
    
    # 调用drive_manager时传递额外参数
    file_list = await drive_manager.get_disk_list(
        x_token, 
        params,
        db=db,
        drive_account_id=drive_account_id
    )
    page_data = paging_list_data(file_list, page_params)
    return response_base.success(data=page_data)


@router.get(
    '/listshare',
    summary='获取分享文件列表',
    description='获取分享来源的文件列表，支持缓存加速',
    response_model=ResponseSchemaModel[PageData[BaseFileInfo]],
    dependencies=[DependsJwtAuth, DependsPagination]
)
async def get_share_file_list(
    db: CurrentSession,
    request: Request,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: Annotated[ListShareFilesParam, Depends()],
    page_params: Annotated[_CustomPageParams, DependsPagination]
) -> ResponseSchemaModel[PageData[BaseFileInfo]]:
    """获取分享文件列表，支持智能缓存"""
    drive_manager = get_drive_manager()
    
    # 从x-token(cookies)获取网盘账户ID
    drive_account_id = None
    try:
        from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
        # x-token就是cookies，直接通过cookies获取对应的网盘账户ID
        drive_account_id = await drive_account_dao.get_id_by_cookies(db, x_token)
    except Exception as e:
        # 如果获取账户ID失败，不影响正常功能，只是不使用缓存
        pass
    
    # 调用drive_manager时传递额外参数
    file_list = await drive_manager.get_share_list(
        x_token, 
        params,
        db=db,
        drive_account_id=drive_account_id
    )
    page_data = paging_list_data(file_list, page_params)
    return response_base.success(data=page_data)


@router.post(
    '/mkdir',
    summary='创建文件夹',
    description='在网盘中创建文件夹',
    response_model=ResponseSchemaModel[BaseFileInfo],
    dependencies=[DependsJwtAuth]
)
async def create_folder(
    x_token: Annotated[str, Header(description="认证令牌")],
    params: MkdirParam
) -> ResponseSchemaModel[BaseFileInfo]:
    drive_manager = get_drive_manager()
    folder_info = await drive_manager.create_mkdir(x_token, params)
    return response_base.success(data=folder_info)


@router.delete(
    '/remove',
    summary='删除文件或文件夹',
    description='删除网盘中的文件或文件夹',
    response_model=ResponseSchemaModel[bool],
    dependencies=[DependsJwtAuth]
)
async def remove_files(
    x_token: Annotated[str, Header(description="认证令牌")],
    params: RemoveParam
) -> ResponseSchemaModel[bool]:
    drive_manager = get_drive_manager()
    result = await drive_manager.remove_files(x_token, params)
    return response_base.success(data=result)


@router.post(
    '/transfer',
    summary='转存文件',
    description='从分享来源转存文件到自己的网盘',
    response_model=ResponseSchemaModel[bool],
    dependencies=[DependsJwtAuth]
)
async def transfer_files(
    x_token: Annotated[str, Header(description="认证令牌")],
    params: TransferParam
) -> ResponseSchemaModel[bool]:
    drive_manager = get_drive_manager()
    result = await drive_manager.transfer_files(x_token, params)
    return response_base.success(data=result)
