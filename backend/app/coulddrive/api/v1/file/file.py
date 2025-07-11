#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated, List

from fastapi import APIRouter, Depends, Header, Request

from backend.app.coulddrive.schema.file import (
    BaseFileInfo, 
    BaseShareInfo,
    ListFilesParam, 
    ListShareFilesParam,
    ListShareInfoParam,
    MkdirParam,
    RemoveParam,
    ShareParam,
    TransferParam,
    CancelShareParam
)
from backend.app.coulddrive.service.yp_service import get_drive_manager
from backend.common.pagination import DependsPagination, PageData, paging_list_data, _CustomPageParams
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('/list', summary='获取文件列表', description='获取网盘文件列表，支持缓存加速', response_model=ResponseSchemaModel[PageData[BaseFileInfo]], dependencies=[DependsJwtAuth, DependsPagination])
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


@router.get(
    '/shareinfo',
    summary='获取分享详情信息',
    description='获取分享详情信息，支持外部分享链接信息获取和本地分享列表获取',
    response_model=ResponseSchemaModel[List[BaseShareInfo]],
    dependencies=[DependsJwtAuth]
)
async def get_share_info(
    db: CurrentSession,
    request: Request,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: Annotated[ListShareInfoParam, Depends()]
) -> ResponseSchemaModel[List[BaseShareInfo]]:
    """
    获取分享详情信息
    
    :param db: 数据库会话
    :param request: 请求对象
    :param x_token: 认证令牌
    :param params: 分享详情查询参数
    :return: 分享详情信息列表
    """
    drive_manager = get_drive_manager()
    
    # 调用drive_manager获取分享信息
    share_info_result = await drive_manager.get_share_info(x_token, params)
    
    # 如果返回的是包含分页信息的字典，提取列表部分
    if isinstance(share_info_result, dict) and 'list' in share_info_result:
        share_info_list = share_info_result['list']
    else:
        share_info_list = share_info_result
    
    return response_base.success(data=share_info_list)


@router.post(
    '/share',
    summary='创建分享链接',
    description='创建文件或文件夹的分享链接',
    response_model=ResponseSchemaModel[BaseShareInfo],
    dependencies=[DependsJwtAuth]
)
async def create_share(
    x_token: Annotated[str, Header(description="认证令牌")],
    params: ShareParam
) -> ResponseSchemaModel[BaseShareInfo]:
    """
    创建分享链接
    
    :param x_token: 认证令牌
    :param params: 分享参数
    :return: 分享信息
    """
    drive_manager = get_drive_manager()
    share_info = await drive_manager.create_share(x_token, params)
    return response_base.success(data=share_info)


@router.delete(
    '/share/cancel',
    summary='取消分享链接',
    description='取消已创建的分享链接',
    response_model=ResponseSchemaModel[bool],
    dependencies=[DependsJwtAuth]
)
async def cancel_share(
    x_token: Annotated[str, Header(description="认证令牌")],
    params: CancelShareParam
) -> ResponseSchemaModel[bool]:
    """
    取消分享链接
    
    :param x_token: 认证令牌
    :param params: 取消分享参数
    :return: 是否成功取消
    """
    drive_manager = get_drive_manager()
    result = await drive_manager.cancel_share(x_token, params)
    return response_base.success(data=result)
