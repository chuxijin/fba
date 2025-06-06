#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.crud.crud_filesync import sync_config_dao
from backend.app.coulddrive.schema.filesync import GetSyncConfigListParam, GetSyncConfigDetail, CreateSyncConfigParam, UpdateSyncConfigParam
from backend.app.coulddrive.schema.enum import DriveType
from backend.common.pagination import DependsPagination, PageData, paging_data, _CustomPageParams
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get(
    "/config", 
    summary="获取同步配置列表",
    response_model=ResponseSchemaModel[PageData[GetSyncConfigDetail]],
    dependencies=[DependsJwtAuth, DependsPagination]
)
async def get_sync_config_list(
    db: CurrentSession,
    params: Annotated[GetSyncConfigListParam, Depends()],
    page_params: Annotated[_CustomPageParams, DependsPagination],
) -> ResponseSchemaModel[PageData[GetSyncConfigDetail]]:
    """
    获取同步配置列表
    
    :param db: 数据库会话
    :param params: 查询参数
    :param page_params: 分页参数
    :return: 同步配置列表
    """
    select_stmt = sync_config_dao.get_list_select(
        enable=params.enable,
        type=params.type.value if params.type else None,
        remark=params.remark,
        created_by=params.created_by,
    )
    page_data = await paging_data(db, select_stmt)
    return response_base.success(data=page_data)


@router.post(
    "/config",
    summary="创建同步配置",
    response_model=ResponseSchemaModel[GetSyncConfigDetail],
    dependencies=[DependsJwtAuth]
)
async def create_sync_config(
    request: Request,
    db: CurrentSession,
    obj: CreateSyncConfigParam,
) -> ResponseSchemaModel[GetSyncConfigDetail]:
    """
    创建同步配置
    
    :param request: 请求对象
    :param db: 数据库会话
    :param obj: 创建参数
    :return: 创建的同步配置详情
    """
    current_user_id = request.user.id
    new_config = await sync_config_dao.create(db, obj_in=obj, current_user_id=current_user_id)
    return response_base.success(data=new_config)


@router.put(
    "/config/{config_id}",
    summary="更新同步配置",
    response_model=ResponseSchemaModel[GetSyncConfigDetail],
    dependencies=[DependsJwtAuth]
)
async def update_sync_config(
    config_id: int,
    db: CurrentSession,
    obj: UpdateSyncConfigParam,
) -> ResponseSchemaModel[GetSyncConfigDetail]:
    """
    更新同步配置
    
    :param config_id: 配置ID
    :param db: 数据库会话
    :param obj: 更新参数
    :return: 更新后的同步配置详情
    """
    db_obj = await sync_config_dao.select_model(db, config_id)
    if not db_obj:
        return response_base.fail(message=f"同步配置 {config_id} 不存在")
    
    updated_config = await sync_config_dao.update(db, db_obj=db_obj, obj_in=obj)
    return response_base.success(data=updated_config)


@router.delete(
    "/config/{config_id}",
    summary="删除同步配置",
    response_model=ResponseSchemaModel[dict],
    dependencies=[DependsJwtAuth]
)
async def delete_sync_config(
    config_id: int,
    db: CurrentSession,
) -> ResponseSchemaModel[dict]:
    """
    删除同步配置
    
    :param config_id: 配置ID
    :param db: 数据库会话
    :return: 删除结果
    """
    success = await sync_config_dao.delete(db, id=config_id)
    if not success:
        return response_base.fail(message=f"同步配置 {config_id} 不存在或删除失败")
    
    return response_base.success(data={"message": "删除成功"}) 