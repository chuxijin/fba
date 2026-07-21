#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.mydrive.schema.public_resource import (
    MyDrivePublicResourceClickResult,
    MyDrivePublicResourceDetail,
    MyDrivePublicResourceListItem,
)
from backend.app.mydrive.service.resource_service import mydrive_resource_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('', summary='公开资源列表', dependencies=[DependsPagination])
async def get_public_resource_list(
    db: CurrentSession,
    category_id: int | None = None,
    resource_type: str | None = None,
    keyword: str | None = None,
    sort_by: str = 'created_time',
    sort_order: str = 'desc',
) -> ResponseSchemaModel[PageData[MyDrivePublicResourceListItem]]:
    """获取公开资源列表（已启用且审核通过）。"""
    from backend.app.mydrive.schema.resource import GetMyDriveResourceListParam

    params = GetMyDriveResourceListParam(
        category_id=category_id,
        resource_type=resource_type,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return response_base.success(data=await mydrive_resource_service.get_public_list(db, params=params))


@router.get(
    '/hot',
    summary='公开热门资源列表',
    response_model=ResponseSchemaModel[list[MyDrivePublicResourceListItem]],
)
async def get_public_hot_resource_list(
    db: CurrentSession,
    category_id: Annotated[int | None, Query(description='分类 ID')] = None,
    resource_types: Annotated[list[str] | None, Query(description='资源类型列表')] = None,
    limit: Annotated[int, Query(description='数量限制', ge=1, le=50)] = 20,
) -> ResponseSchemaModel[list[MyDrivePublicResourceListItem]]:
    """获取公开热门资源列表（按热度排序）。"""
    return response_base.success(
        data=await mydrive_resource_service.get_public_hot_list(
            db, category_id=category_id, resource_types=resource_types, limit=limit
        )
    )


@router.get(
    '/{pk}',
    summary='公开资源详情',
    response_model=ResponseSchemaModel[MyDrivePublicResourceDetail],
)
async def get_public_resource_detail(
    db: CurrentSession,
    pk: Annotated[int, Path(description='资源 ID')],
) -> ResponseSchemaModel[MyDrivePublicResourceDetail]:
    """获取公开资源详情。"""
    return response_base.success(data=await mydrive_resource_service.get_public_detail(db, pk=pk))


@router.post(
    '/{pk}/click',
    summary='记录公开资源点击',
    response_model=ResponseSchemaModel[MyDrivePublicResourceClickResult],
)
async def record_public_resource_click(
    db: CurrentSession,
    pk: Annotated[int, Path(description='资源 ID')],
) -> ResponseSchemaModel[MyDrivePublicResourceClickResult]:
    """记录公开资源点击事件（用于热度计算）。"""
    return response_base.success(data=await mydrive_resource_service.record_public_view(db, pk=pk))
