#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from backend.app.mcp.schema.config import GetMcpConfigListParam, UpsertMcpConfigBatchParam, UpsertMcpConfigParam
from backend.app.mcp.service.config_service import mcp_config_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter(prefix='/config')


@router.get(
    '/',
    summary='配置列表',
    dependencies=[DependsJwtAuth],
    response_model=ResponseSchemaModel[list],
    name='get_mcp_config_list',
)
async def get_mcp_config_list(
    db: CurrentSession,
    params: Annotated[GetMcpConfigListParam, Depends()],
) -> ResponseSchemaModel[list]:
    items = await mcp_config_service.get_list(db, params.mcp, params.field)
    return response_base.success(data=[{'id': i.id, 'mcp': i.mcp, 'field': i.field, 'value': i.value} for i in items])


@router.get(
    '/{config_id}',
    summary='配置详情',
    dependencies=[DependsJwtAuth],
    response_model=ResponseSchemaModel[dict],
    name='get_mcp_config_detail',
)
async def get_mcp_config_detail(db: CurrentSession, config_id: int) -> ResponseSchemaModel[dict]:
    obj = await mcp_config_service.get(db, config_id)
    return response_base.success(
        data={'id': obj.id, 'mcp': obj.mcp, 'field': obj.field, 'value': obj.value} if obj else None
    )


@router.post(
    '/',
    summary='新增或更新配置',
    dependencies=[DependsJwtAuth],
    response_model=ResponseSchemaModel[dict],
    name='upsert_mcp_config',
)
async def upsert_mcp_config(
    request: Request,
    db: CurrentSession,
    data: UpsertMcpConfigParam,
) -> ResponseSchemaModel[dict]:
    existing = await mcp_config_service.get_by_mcp_and_field(db, data.mcp, data.field)
    if existing:
        obj = await mcp_config_service.update(db, data, request.user.id)
    else:
        obj = await mcp_config_service.create(db, data, created_by=request.user.id)
    return response_base.success(data={'id': obj.id, 'mcp': obj.mcp, 'field': obj.field, 'value': obj.value})


@router.post(
    '/batch',
    summary='批量新增或更新配置',
    dependencies=[DependsJwtAuth],
    response_model=ResponseSchemaModel[list],
    name='upsert_mcp_config_batch',
)
async def upsert_mcp_config_batch(
    request: Request,
    db: CurrentSession,
    data: UpsertMcpConfigBatchParam,
) -> ResponseSchemaModel[list]:
    results = await mcp_config_service.upsert_batch(db, data, request.user.id)
    return response_base.success(data=[{'id': i.id, 'mcp': i.mcp, 'field': i.field, 'value': i.value} for i in results])


@router.delete(
    '/{config_id}',
    summary='删除配置',
    dependencies=[DependsJwtAuth],
    response_model=ResponseModel,
    name='delete_mcp_config',
)
async def delete_mcp_config(db: CurrentSession, config_id: int) -> ResponseModel:
    await mcp_config_service.delete(db, config_id)
    return response_base.success()
