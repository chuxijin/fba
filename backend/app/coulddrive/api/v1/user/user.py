#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from backend.app.coulddrive.schema.file import (
    BaseFileInfo, 
    ListFilesParam, 
    ListShareFilesParam,
    MkdirParam,
    RelationshipParam,
    RemoveParam,
    TransferParam,
    UserInfoParam
)
from backend.app.coulddrive.schema.user import BaseUserInfo, RelationshipItem, GetUserListParam, CoulddriveDriveAccountDetail, CreateDriveAccountParam, UpdateDriveAccountParam
from backend.app.coulddrive.service.yp_service import get_drive_manager
from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.common.pagination import DependsPagination, PageData, paging_list_data, _CustomPageParams
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()

@router.get(
    '/userinfo',
    summary='获取用户信息',
    description='获取用户信息',
    response_model=ResponseSchemaModel[BaseUserInfo],
    dependencies=[DependsJwtAuth]
)
async def get_user_info(
    x_token: Annotated[str, Header(description="认证令牌")],
    params: Annotated[UserInfoParam, Depends()],
) -> ResponseSchemaModel[BaseUserInfo]:
    drive_manager = get_drive_manager()
    user_info = await drive_manager.get_user_info(x_token, params)
    return response_base.success(data=user_info)

@router.get(
    '/relationshiplist',
    summary='获取关系列表',
    description='获取网盘关系列表',
    response_model=ResponseSchemaModel[PageData[RelationshipItem]],
    dependencies=[DependsJwtAuth, DependsPagination]
)
async def get_relationship_list(
    x_token: Annotated[str, Header(description="认证令牌")],
    params: Annotated[RelationshipParam, Depends()],
    page_params: Annotated[_CustomPageParams, DependsPagination]
) -> ResponseSchemaModel[PageData[RelationshipItem]]:
    drive_manager = get_drive_manager()
    relationship_list = await drive_manager.get_relationship_list(x_token, params)
    page_data = paging_list_data(relationship_list, page_params)
    return response_base.success(data=page_data)


@router.get(
    '/userlist',
    summary='获取用户列表',
    description='获取数据库中的所有网盘用户信息',
    response_model=ResponseSchemaModel[PageData[CoulddriveDriveAccountDetail]],
    dependencies=[DependsJwtAuth, DependsPagination]
)
async def get_user_list(
    db: CurrentSession,
    params: Annotated[GetUserListParam, Depends()],
    page_params: Annotated[_CustomPageParams, DependsPagination]
) -> ResponseSchemaModel[PageData[CoulddriveDriveAccountDetail]]:
    """
    获取数据库中的所有网盘用户信息
    
    :param db: 数据库会话
    :param params: 查询参数
    :param page_params: 分页参数
    :return:
    """
    user_list = await drive_account_dao.get_list_with_pagination(
        db, 
        type=params.type, 
        is_valid=params.is_valid
    )
    page_data = paging_list_data(user_list, page_params)
    return response_base.success(data=page_data)


@router.post(
    '/create',
    summary='创建网盘用户',
    response_model=ResponseSchemaModel[BaseUserInfo],
    dependencies=[DependsJwtAuth]
)
async def create_user(
    request: Request,
    db: CurrentSession,
    x_token: Annotated[str, Header(description="认证令牌")],
    params: Annotated[UserInfoParam, Depends()],
) -> ResponseSchemaModel[BaseUserInfo]:
    """
    创建网盘用户
    
    :param request: 请求对象
    :param db: 数据库会话
    :param x_token: 认证令牌
    :param params: 用户信息参数
    :return: 用户信息
    """
    # 获取用户信息
    user_info_response = await get_user_info(x_token, params)
    user_data = user_info_response.data
    
    # 创建或更新用户
    drive_type_str = params.drive_type.value if hasattr(params.drive_type, 'value') else params.drive_type
    await drive_account_dao.create_or_update(
        db, user_data, drive_type_str, x_token, request.user.id
    )
    
    return response_base.success(data=user_data)


@router.delete(
    '/{user_id}',
    summary='删除网盘用户',
    response_model=ResponseSchemaModel[str],
    dependencies=[DependsJwtAuth],
    name='delete_coulddrive_user'
)
async def delete_coulddrive_user(
    user_id: int,
    db: CurrentSession,
) -> ResponseSchemaModel[str]:
    """
    删除网盘用户
    
    :param user_id: 用户ID
    :param db: 数据库会话
    :return: 删除结果
    """
    result = await drive_account_dao.delete(db, [user_id])
    if result > 0:
        return response_base.success(data="删除成功")
    else:
        return response_base.fail(msg="删除失败，用户不存在")