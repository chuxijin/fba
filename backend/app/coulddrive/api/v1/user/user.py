#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Header

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
from backend.app.coulddrive.schema.user import BaseUserInfo, RelationshipItem
from backend.app.coulddrive.service.yp_service import get_drive_manager
from backend.common.pagination import DependsPagination, PageData, paging_list_data, _CustomPageParams
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth

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