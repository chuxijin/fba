#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession
from backend.plugin.mcp_service.schema.mcp_config import McpConfigIn, McpConfigOut
from backend.plugin.mcp_service.service.mcp_config_service import mcp_config_service


router = APIRouter()


@router.get('/{pk}', summary='获取 MCP 配置详情', dependencies=[DependsJwtAuth])
async def get_mcp_config(pk: Annotated[int, Path(description='配置 ID')]) -> ResponseSchemaModel[McpConfigOut]:
    config = await mcp_config_service.get(pk=pk)
    data = McpConfigOut(id=config.id, mcp=config.mcp, config=config.config)
    return response_base.success(data=data)


@router.get('/', summary='分页获取 MCP 配置', dependencies=[DependsJwtAuth, DependsPagination])
async def get_mcp_configs_paged(db: CurrentSession) -> ResponseSchemaModel[PageData[McpConfigOut]]:
    select_stmt = await mcp_config_service.get_select()
    page = await paging_data(db, select_stmt)
    return response_base.success(data=page)


@router.post('/', summary='创建 MCP 配置', dependencies=[DependsRBAC])
async def create_mcp_config(obj: McpConfigIn) -> ResponseSchemaModel[McpConfigOut]:
    config = await mcp_config_service.create(obj=obj)
    data = McpConfigOut(id=config.id, mcp=config.mcp, config=config.config)
    return response_base.success(data=data)


@router.put('/{pk}', summary='更新 MCP 配置', dependencies=[DependsRBAC])
async def update_mcp_config(pk: Annotated[int, Path(description='配置 ID')], obj: McpConfigIn) -> ResponseModel:
    count = await mcp_config_service.update(pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post('/upsert', summary='新增或更新 MCP 配置', dependencies=[DependsRBAC, DependsJwtAuth])
async def upsert_mcp_config(request: Request, obj: McpConfigIn) -> ResponseSchemaModel[McpConfigOut]:
    created_by = request.user.id
    config = await mcp_config_service.upsert(obj=obj, created_by=created_by)
    data = McpConfigOut(id=config.id, mcp=config.mcp, config=config.config)
    return response_base.success(data=data)


@router.delete('/', summary='批量删除 MCP 配置', dependencies=[DependsRBAC])
async def delete_mcp_configs(pks: list[int]) -> ResponseModel:
    count = await mcp_config_service.delete(pks=pks)
    if count > 0:
        return response_base.success()
    return response_base.fail()


