#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile

from backend.app.gongkao.schema.resource import (
    CreateResourceParam,
    GetResourceDetail,
    GetResourceListParams,
    UpdateResourceParam,
)
from backend.app.gongkao.service.resource_service import resource_service
from backend.common.exception import errors
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('', summary='获取资料列表', name='get_gk_resource_list', dependencies=[DependsPagination])
async def get_gk_resource_list(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='标题')] = None,
    category_id: Annotated[int | None, Query(description='分类 ID')] = None,
    file_type: Annotated[str | None, Query(description='文件类型')] = None,
) -> ResponseModel:
    """获取资料列表（公开）"""
    stmt = await resource_service.get_list(
        db,
        title=title,
        category_id=category_id,
        file_type=file_type,
        status=True,
    )
    page_data = await paging_data(db, stmt, schema_cls=GetResourceDetail)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取资料详情', name='get_gk_resource_detail')
async def get_gk_resource_detail(pk: int, db: CurrentSession) -> ResponseModel:
    """获取资料详情（公开）"""
    resource = await resource_service.get(db, pk)
    if not resource:
        raise errors.NotFoundError(msg='资料不存在')
    return response_base.success(data=GetResourceDetail.model_validate(resource))


@router.post('/{pk}/view', summary='增加查看次数', name='increment_gk_resource_view_count')
async def increment_gk_resource_view_count(pk: int, db: CurrentSessionTransaction) -> ResponseModel:
    """增加资料查看次数"""
    count = await resource_service.increment_view(db, pk)
    return response_base.success(data={'view_count': count})


@router.post('', summary='创建资料', dependencies=[DependsJwtAuth], name='create_gk_resource')
async def create_gk_resource(obj_in: CreateResourceParam, db: CurrentSessionTransaction) -> ResponseModel:
    """创建资料（需登录）"""
    resource = await resource_service.create(db, obj_in)
    return response_base.success(data=GetResourceDetail.model_validate(resource))


@router.put('/{pk}', summary='更新资料', dependencies=[DependsJwtAuth], name='update_gk_resource')
async def update_gk_resource(pk: int, obj_in: UpdateResourceParam, db: CurrentSessionTransaction) -> ResponseModel:
    """更新资料（需登录）"""
    count = await resource_service.update(db, pk, obj_in)
    if count == 0:
        raise errors.NotFoundError(msg='资料不存在')
    return response_base.success()


@router.delete('/{pk}', summary='删除资料', dependencies=[DependsJwtAuth], name='delete_gk_resource')
async def delete_gk_resource(pk: int, db: CurrentSessionTransaction) -> ResponseModel:
    """删除资料（需登录）"""
    count = await resource_service.delete(db, pk)
    if count == 0:
        raise errors.NotFoundError(msg='资料不存在')
    return response_base.success()


@router.post('/upload', summary='上传资料文件', dependencies=[DependsJwtAuth], name='upload_gk_resource_file')
async def upload_gk_resource_file(
    file: Annotated[UploadFile, File()],
    category_id: Annotated[int, Query(description='分类 ID')],
    db: CurrentSession,
) -> ResponseModel:
    """上传资料预览文件，文件将保存到 static/gk_resource/{分类路径}/ 目录下"""
    result = await resource_service.upload_file(db, file, category_id)
    return response_base.success(data=result)
