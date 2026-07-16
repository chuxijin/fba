#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Request

from backend.app.mydrive.schema.sync import (
    CreateMyDriveSyncConfigParam,
    CreateMyDriveSyncRuleSetParam,
    GetMyDriveSyncConfigDetail,
    GetMyDriveSyncRuleSetDetail,
    GetMyDriveSyncRuleSetListItem,
    GetMyDriveSyncTaskDetail,
    GetMyDriveSyncTaskItemDetail,
    UpdateMyDriveSyncConfigParam,
    UpdateMyDriveSyncRuleSetParam,
)
from backend.app.mydrive.service.sync_service import mydrive_sync_service
from backend.app.task.tasks.mydrive.tasks import execute_mydrive_sync_task
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/rule-sets', summary='分页获取同步规则集', dependencies=[DependsJwtAuth, DependsPagination])
async def get_mydrive_sync_rule_sets(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[PageData[GetMyDriveSyncRuleSetListItem]]:
    """分页获取当前用户的同步规则集。"""
    stmt = await mydrive_sync_service.get_rule_set_select(request.user.id)
    return response_base.success(data=await paging_data(db, stmt))


@router.get('/rule-sets/{pk}', summary='获取同步规则集', dependencies=[DependsJwtAuth])
async def get_mydrive_sync_rule_set(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='规则集 ID')],
) -> ResponseSchemaModel[GetMyDriveSyncRuleSetDetail]:
    """获取当前用户的同步规则集详情。"""
    return response_base.success(data=await mydrive_sync_service.get_rule_set(db, pk=pk, owner_id=request.user.id))


@router.post('/rule-sets', summary='创建同步规则集', dependencies=[DependsJwtAuth])
async def create_mydrive_sync_rule_set(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateMyDriveSyncRuleSetParam,
) -> ResponseSchemaModel[GetMyDriveSyncRuleSetDetail]:
    """创建当前用户的同步规则集。"""
    rule_set = await mydrive_sync_service.create_rule_set(db, owner_id=request.user.id, obj=obj)
    return response_base.success(data=rule_set)


@router.put('/rule-sets/{pk}', summary='更新同步规则集', dependencies=[DependsJwtAuth])
async def update_mydrive_sync_rule_set(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='规则集 ID')],
    obj: UpdateMyDriveSyncRuleSetParam,
) -> ResponseModel:
    """更新当前用户的同步规则集。"""
    await mydrive_sync_service.update_rule_set(db, pk=pk, owner_id=request.user.id, obj=obj)
    return response_base.success()


@router.delete('/rule-sets/{pk}', summary='删除同步规则集', dependencies=[DependsJwtAuth])
async def delete_mydrive_sync_rule_set(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='规则集 ID')],
) -> ResponseModel:
    """删除当前用户的同步规则集。"""
    await mydrive_sync_service.delete_rule_set(db, pk=pk, owner_id=request.user.id)
    return response_base.success()


@router.get('/configs', summary='分页获取同步配置', dependencies=[DependsJwtAuth, DependsPagination])
async def get_mydrive_sync_configs(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[PageData[GetMyDriveSyncConfigDetail]]:
    """分页获取当前用户的同步配置。"""
    stmt = await mydrive_sync_service.get_config_select(request.user.id)
    return response_base.success(data=await paging_data(db, stmt))


@router.get('/configs/{pk}', summary='获取同步配置', dependencies=[DependsJwtAuth])
async def get_mydrive_sync_config(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='同步配置 ID')],
) -> ResponseSchemaModel[GetMyDriveSyncConfigDetail]:
    """获取当前用户的同步配置详情。"""
    return response_base.success(data=await mydrive_sync_service.get_config(db, pk=pk, owner_id=request.user.id))


@router.post('/configs', summary='创建同步配置', dependencies=[DependsJwtAuth])
async def create_mydrive_sync_config(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateMyDriveSyncConfigParam,
) -> ResponseSchemaModel[GetMyDriveSyncConfigDetail]:
    """创建当前用户的同步配置。"""
    config = await mydrive_sync_service.create_config(db, owner_id=request.user.id, obj=obj)
    return response_base.success(data=config)


@router.put('/configs/{pk}', summary='更新同步配置', dependencies=[DependsJwtAuth])
async def update_mydrive_sync_config(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='同步配置 ID')],
    obj: UpdateMyDriveSyncConfigParam,
) -> ResponseModel:
    """更新当前用户的同步配置。"""
    await mydrive_sync_service.update_config(db, pk=pk, owner_id=request.user.id, obj=obj)
    return response_base.success()


@router.delete('/configs/{pk}', summary='删除同步配置', dependencies=[DependsJwtAuth])
async def delete_mydrive_sync_config(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='同步配置 ID')],
) -> ResponseModel:
    """删除当前用户的同步配置。"""
    await mydrive_sync_service.delete_config(db, pk=pk, owner_id=request.user.id)
    return response_base.success()


@router.post('/configs/{pk}/tasks', summary='创建同步任务', dependencies=[DependsJwtAuth])
async def create_mydrive_sync_task(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='同步配置 ID')],
) -> ResponseSchemaModel[GetMyDriveSyncTaskDetail]:
    """为当前用户的同步配置创建待执行任务。"""
    task = await mydrive_sync_service.create_task(db, config_id=pk, owner_id=request.user.id)
    await db.commit()
    await db.refresh(task)
    execute_mydrive_sync_task.delay(task.id)
    return response_base.success(data=task)


@router.get('/tasks', summary='分页获取同步任务', dependencies=[DependsJwtAuth, DependsPagination])
async def get_mydrive_sync_tasks(
    request: Request,
    db: CurrentSession,
    config_id: int | None = None,
) -> ResponseSchemaModel[PageData[GetMyDriveSyncTaskDetail]]:
    """分页获取当前用户的同步任务。"""
    stmt = await mydrive_sync_service.get_task_select(request.user.id, config_id)
    return response_base.success(data=await paging_data(db, stmt))


@router.get('/tasks/{pk}', summary='获取同步任务', dependencies=[DependsJwtAuth])
async def get_mydrive_sync_task(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='同步任务 ID')],
) -> ResponseSchemaModel[GetMyDriveSyncTaskDetail]:
    """获取当前用户的同步任务详情。"""
    return response_base.success(data=await mydrive_sync_service.get_task(db, pk=pk, owner_id=request.user.id))


@router.get('/tasks/{pk}/items', summary='分页获取同步任务明细', dependencies=[DependsJwtAuth, DependsPagination])
async def get_mydrive_sync_task_items(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='同步任务 ID')],
) -> ResponseSchemaModel[PageData[GetMyDriveSyncTaskItemDetail]]:
    """分页获取当前用户同步任务的执行明细。"""
    stmt = await mydrive_sync_service.get_task_item_select(db, task_id=pk, owner_id=request.user.id)
    return response_base.success(data=await paging_data(db, stmt))


@router.post('/tasks/{pk}/cancel', summary='取消同步任务', dependencies=[DependsJwtAuth])
async def cancel_mydrive_sync_task(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='同步任务 ID')],
) -> ResponseModel:
    """请求取消当前用户的同步任务。"""
    await mydrive_sync_service.request_task_cancel(db, pk=pk, owner_id=request.user.id)
    return response_base.success()
