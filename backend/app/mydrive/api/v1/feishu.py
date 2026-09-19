#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.mydrive.schema.feishu import (
    CreateFeishuSheetConfigParam,
    GetFeishuCategorySourceOption,
    GetFeishuSheetConfigDetail,
    GetFeishuSheetTaskDetail,
    UpdateFeishuSheetConfigParam,
)
from backend.app.mydrive.service.feishu_export_service import mydrive_feishu_export_service
from backend.app.task.tasks.feishu.tasks import execute_feishu_export_task
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/category-sources', summary='获取可选分类来源', dependencies=[DependsJwtAuth])
async def get_feishu_category_sources(
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetFeishuCategorySourceOption]]:
    """获取可选分类来源（app_code + category_type 组合），供管理端下拉选择。"""
    return response_base.success(data=await mydrive_feishu_export_service.list_category_sources(db))


@router.get('/configs', summary='分页获取飞书表导出配置', dependencies=[DependsJwtAuth, DependsPagination])
async def get_feishu_sheet_configs(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='配置名称（模糊匹配）')] = None,
    is_enabled: Annotated[bool | None, Query(description='是否启用')] = None,
) -> ResponseSchemaModel[PageData[GetFeishuSheetConfigDetail]]:
    """分页获取飞书表导出配置。"""
    stmt = await mydrive_feishu_export_service.get_config_select(name, is_enabled=is_enabled)
    return response_base.success(data=await paging_data(db, stmt))


@router.get('/configs/{pk}', summary='获取飞书表导出配置', dependencies=[DependsJwtAuth])
async def get_feishu_sheet_config(
    db: CurrentSession,
    pk: Annotated[int, Path(description='导出配置 ID')],
) -> ResponseSchemaModel[GetFeishuSheetConfigDetail]:
    """获取飞书表导出配置详情。"""
    return response_base.success(data=await mydrive_feishu_export_service.get_config(db, pk=pk))


@router.post('/configs', summary='创建飞书表导出配置', dependencies=[DependsJwtAuth])
async def create_feishu_sheet_config(
    db: CurrentSessionTransaction,
    obj: CreateFeishuSheetConfigParam,
) -> ResponseSchemaModel[GetFeishuSheetConfigDetail]:
    """创建飞书表导出配置。"""
    config = await mydrive_feishu_export_service.create_config(db, obj=obj)
    return response_base.success(data=config)


@router.put('/configs/{pk}', summary='更新飞书表导出配置', dependencies=[DependsJwtAuth])
async def update_feishu_sheet_config(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='导出配置 ID')],
    obj: UpdateFeishuSheetConfigParam,
) -> ResponseModel:
    """更新飞书表导出配置。"""
    await mydrive_feishu_export_service.update_config(db, pk=pk, obj=obj)
    return response_base.success()


@router.delete('/configs/{pk}', summary='删除飞书表导出配置', dependencies=[DependsJwtAuth])
async def delete_feishu_sheet_config(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='导出配置 ID')],
) -> ResponseModel:
    """删除飞书表导出配置。"""
    await mydrive_feishu_export_service.delete_config(db, pk=pk)
    return response_base.success()


@router.post('/configs/{pk}/tasks', summary='手动执行飞书表导出', dependencies=[DependsJwtAuth])
async def create_feishu_sheet_task(
    db: CurrentSession,
    pk: Annotated[int, Path(description='导出配置 ID')],
) -> ResponseSchemaModel[GetFeishuSheetTaskDetail]:
    """为飞书表导出配置创建待执行任务并立即派发。"""
    task = await mydrive_feishu_export_service.create_task(db, config_id=pk, manual=True)
    await db.commit()
    await db.refresh(task)
    execute_feishu_export_task.delay(task.id)
    return response_base.success(data=task)


@router.get('/tasks', summary='分页获取飞书表导出任务', dependencies=[DependsJwtAuth, DependsPagination])
async def get_feishu_sheet_tasks(
    db: CurrentSession,
    config_id: Annotated[int | None, Query(description='导出配置 ID')] = None,
    status: Annotated[str | None, Query(description='任务状态')] = None,
) -> ResponseSchemaModel[PageData[GetFeishuSheetTaskDetail]]:
    """分页获取飞书表导出任务。"""
    stmt = await mydrive_feishu_export_service.get_task_select(config_id, status)
    return response_base.success(data=await paging_data(db, stmt))


@router.get('/tasks/{pk}', summary='获取飞书表导出任务', dependencies=[DependsJwtAuth])
async def get_feishu_sheet_task(
    db: CurrentSession,
    pk: Annotated[int, Path(description='导出任务 ID')],
) -> ResponseSchemaModel[GetFeishuSheetTaskDetail]:
    """获取飞书表导出任务详情。"""
    return response_base.success(data=await mydrive_feishu_export_service.get_task(db, pk=pk))
