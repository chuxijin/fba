#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.coulddrive.schema.file_cache import (
    CreateFileCacheParam,
    UpdateFileCacheParam,
    FileCacheQueryParam,
    BatchCreateFileCacheParam,
    GetFileCacheDetail,
    GetFileCacheStats,
    FileCacheStatsParam
)
from backend.app.coulddrive.service.file_cache_service import file_cache_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('/{cache_id}', summary='获取文件缓存详情', dependencies=[DependsJwtAuth])
async def get_file_cache(
    db: CurrentSession,
    cache_id: Annotated[int, Path(..., description='缓存ID')]
) -> ResponseSchemaModel[GetFileCacheDetail]:
    """获取文件缓存详情"""
    cache = await file_cache_service.get_file_cache(db, cache_id=cache_id)
    return response_base.success(data=cache)


@router.get('/file/{file_id}', summary='通过文件ID获取缓存', dependencies=[DependsJwtAuth])
async def get_file_cache_by_file_id(
    db: CurrentSession,
    file_id: Annotated[str, Path(..., description='文件ID')],
    drive_account_id: Annotated[int, Query(..., description='网盘账户ID')]
) -> ResponseSchemaModel[GetFileCacheDetail | None]:
    """通过文件ID获取缓存"""
    cache = await file_cache_service.get_file_cache_by_file_id(
        db, file_id=file_id, drive_account_id=drive_account_id
    )
    return response_base.success(data=cache)


@router.get('/path', summary='通过文件路径获取缓存', dependencies=[DependsJwtAuth])
async def get_file_cache_by_path(
    db: CurrentSession,
    file_path: Annotated[str, Query(..., description='文件路径')],
    drive_account_id: Annotated[int, Query(..., description='网盘账户ID')]
) -> ResponseSchemaModel[GetFileCacheDetail | None]:
    """通过文件路径获取缓存"""
    cache = await file_cache_service.get_file_cache_by_path(
        db, file_path=file_path, drive_account_id=drive_account_id
    )
    return response_base.success(data=cache)


@router.get('/children/{parent_id}', summary='获取子文件列表', dependencies=[DependsJwtAuth])
async def get_children_files(
    db: CurrentSession,
    parent_id: Annotated[str, Path(..., description='父目录ID')],
    drive_account_id: Annotated[int, Query(..., description='网盘账户ID')],
    is_valid: Annotated[bool, Query(description='是否只获取有效缓存')] = True
) -> ResponseSchemaModel[list[GetFileCacheDetail]]:
    """获取子文件列表"""
    children = await file_cache_service.get_children_files(
        db, parent_id=parent_id, drive_account_id=drive_account_id, is_valid=is_valid
    )
    return response_base.success(data=children)


@router.get('', summary='获取文件缓存列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_file_cache_list(
    db: CurrentSession,
    drive_account_id: Annotated[int | None, Query(description='网盘账户ID')] = None,
    file_path: Annotated[str | None, Query(description='文件路径')] = None,
    parent_id: Annotated[str | None, Query(description='父目录ID')] = None,
    is_folder: Annotated[bool | None, Query(description='是否为文件夹')] = None,
    is_valid: Annotated[bool | None, Query(description='缓存是否有效')] = None,
    cache_version: Annotated[str | None, Query(description='缓存版本')] = None
) -> ResponseSchemaModel[PageData[GetFileCacheDetail]]:
    """获取文件缓存列表"""
    query_param = FileCacheQueryParam(
        drive_account_id=drive_account_id,
        file_path=file_path,
        parent_id=parent_id,
        is_folder=is_folder,
        is_valid=is_valid,
        cache_version=cache_version
    )
    
    cache_select = await file_cache_service.get_file_cache_select(db, query_param=query_param)
    page_data = await paging_data(db, cache_select)
    
    return response_base.success(data=page_data)


@router.post('', summary='创建文件缓存', dependencies=[DependsJwtAuth])
async def create_file_cache(
    db: CurrentSession,
    cache_in: CreateFileCacheParam
) -> ResponseSchemaModel[GetFileCacheDetail]:
    """创建文件缓存"""
    cache = await file_cache_service.create_file_cache(db, cache_in=cache_in)
    return response_base.success(data=cache)


@router.post('/batch', summary='批量创建文件缓存', dependencies=[DependsJwtAuth])
async def batch_create_file_cache(
    db: CurrentSession,
    batch_param: BatchCreateFileCacheParam
) -> ResponseSchemaModel[list[GetFileCacheDetail]]:
    """批量创建文件缓存"""
    caches = await file_cache_service.batch_create_file_cache(db, batch_param=batch_param)
    return response_base.success(data=caches)


@router.put('/{cache_id}', summary='更新文件缓存', dependencies=[DependsJwtAuth])
async def update_file_cache(
    db: CurrentSession,
    cache_id: Annotated[int, Path(..., description='缓存ID')],
    cache_in: UpdateFileCacheParam
) -> ResponseSchemaModel[GetFileCacheDetail]:
    """更新文件缓存"""
    cache = await file_cache_service.update_file_cache(db, cache_id=cache_id, cache_in=cache_in)
    return response_base.success(data=cache)


@router.delete('/{cache_id}', summary='删除文件缓存', dependencies=[DependsJwtAuth])
async def delete_file_cache(
    db: CurrentSession,
    cache_id: Annotated[int, Path(..., description='缓存ID')]
) -> ResponseSchemaModel[bool]:
    """删除文件缓存"""
    result = await file_cache_service.delete_file_cache(db, cache_id=cache_id)
    return response_base.success(data=result)


@router.post('/invalidate', summary='使缓存失效', dependencies=[DependsJwtAuth])
async def invalidate_cache(
    db: CurrentSession,
    drive_account_id: Annotated[int, Query(..., description='网盘账户ID')],
    cache_version: Annotated[str | None, Query(description='缓存版本')] = None
) -> ResponseSchemaModel[int]:
    """使缓存失效"""
    count = await file_cache_service.invalidate_cache(
        db, drive_account_id=drive_account_id, cache_version=cache_version
    )
    return response_base.success(data=count)


@router.delete('/clear', summary='清除缓存', dependencies=[DependsJwtAuth])
async def clear_cache(
    db: CurrentSession,
    drive_account_id: Annotated[int, Query(..., description='网盘账户ID')],
    cache_version: Annotated[str | None, Query(description='缓存版本')] = None
) -> ResponseSchemaModel[int]:
    """清除缓存"""
    count = await file_cache_service.clear_cache(
        db, drive_account_id=drive_account_id, cache_version=cache_version
    )
    return response_base.success(data=count)


@router.get('/stats/summary', summary='获取缓存统计信息', dependencies=[DependsJwtAuth])
async def get_cache_stats(
    db: CurrentSession,
    drive_account_id: Annotated[int | None, Query(description='网盘账户ID')] = None
) -> ResponseSchemaModel[GetFileCacheStats]:
    """获取缓存统计信息"""
    stats_param = FileCacheStatsParam(drive_account_id=drive_account_id)
    stats = await file_cache_service.get_cache_stats(db, stats_param=stats_param)
    return response_base.success(data=stats) 