#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, Path, Query, Request, UploadFile

from backend.app.coulddrive.service.resource_upload_service import (
    ResourceUploadSizeError,
    ResourceUploadTypeError,
    resource_upload_service,
)

from backend.app.mydrive.schema.resource import (
    CreateMyDriveResourceParam,
    GetMyDriveResourceDetail,
    GetMyDriveResourceListParam,
    GetMyDriveResourceStatistics,
    GetMyDriveResourceViewHistoryDetail,
    GetMyDriveResourceViewTrendParam,
    UpdateMyDriveResourceParam,
)
from backend.app.mydrive.service.resource_service import mydrive_resource_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import CustomResponse, ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.post('/upload', summary='上传资源文件', dependencies=[DependsJwtAuth])
async def upload_mydrive_resource_file(
    db: CurrentSession,
    file: Annotated[UploadFile, File(description='文件')],
) -> ResponseModel:
    """上传资源文件并生成缩略图。"""
    try:
        return response_base.success(data=await resource_upload_service.upload_file(db=db, file=file))
    except ResourceUploadSizeError as exc:
        return response_base.fail(res=CustomResponse(code=400, msg=str(exc)))
    except Exception as exc:
        return response_base.fail(res=CustomResponse(code=500, msg=f'文件上传失败: {exc}'))


@router.post('/upload/pdf-previews', summary='上传 PDF 生成资源缩略图', dependencies=[DependsJwtAuth])
async def upload_mydrive_resource_pdf_previews(
    db: CurrentSession,
    file: Annotated[UploadFile, File(description='PDF 文件')],
    page_count: Annotated[int, Query(description='预览页数', ge=1, le=10)] = 3,
    max_side: Annotated[int, Query(description='图片最长边像素', ge=160, le=2000)] = 960,
    quality: Annotated[int, Query(description='JPEG 质量', ge=1, le=95)] = 86,
) -> ResponseModel:
    """上传 PDF 并仅生成资源缩略图。"""
    try:
        data = await resource_upload_service.upload_pdf_previews(
            db=db,
            file=file,
            page_count=page_count,
            max_side=max_side,
            quality=quality,
        )
        return response_base.success(data=data)
    except (ResourceUploadSizeError, ResourceUploadTypeError, ValueError) as exc:
        return response_base.fail(res=CustomResponse(code=400, msg=str(exc)))
    except Exception as exc:
        return response_base.fail(res=CustomResponse(code=500, msg=f'PDF 缩略图生成失败: {exc}'))


@router.get('', summary='分页获取资源', dependencies=[DependsJwtAuth, DependsPagination])
async def get_mydrive_resources(
    request: Request,
    db: CurrentSession,
    category_id: int | None = None,
    resource_type: str | None = None,
    provider: str | None = None,
    status: str | None = None,
    audit_status: str | None = None,
    share_status: str | None = None,
    keyword: str | None = None,
    sort_by: str = 'created_time',
    sort_order: str = 'desc',
) -> ResponseSchemaModel[PageData[GetMyDriveResourceDetail]]:
    """分页获取当前用户资源。"""
    params = GetMyDriveResourceListParam(
        audit_status=audit_status,
        category_id=category_id,
        keyword=keyword,
        provider=provider,
        resource_type=resource_type,
        share_status=share_status,
        sort_by=sort_by,
        sort_order=sort_order,
        status=status,
    )
    return response_base.success(data=await mydrive_resource_service.get_list(db, owner_id=request.user.id, params=params))


@router.get('/statistics', summary='获取资源统计', dependencies=[DependsJwtAuth])
async def get_mydrive_resource_statistics(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[GetMyDriveResourceStatistics]:
    """获取当前用户资源统计。"""
    return response_base.success(data=await mydrive_resource_service.get_statistics(db, owner_id=request.user.id))


@router.get('/{pk}', summary='获取资源详情', dependencies=[DependsJwtAuth])
async def get_mydrive_resource(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='资源 ID')],
) -> ResponseSchemaModel[GetMyDriveResourceDetail]:
    """获取当前用户资源详情。"""
    return response_base.success(data=await mydrive_resource_service.get(db, pk=pk, owner_id=request.user.id))


@router.post('', summary='创建资源', dependencies=[DependsJwtAuth])
async def create_mydrive_resource(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateMyDriveResourceParam,
) -> ResponseSchemaModel[GetMyDriveResourceDetail]:
    """创建当前用户资源。"""
    resource = await mydrive_resource_service.create(db, owner_id=request.user.id, created_by=request.user.id, obj=obj)
    return response_base.success(data=resource)


@router.put('/{pk}', summary='更新资源', dependencies=[DependsJwtAuth])
async def update_mydrive_resource(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='资源 ID')],
    obj: UpdateMyDriveResourceParam,
) -> ResponseSchemaModel[GetMyDriveResourceDetail]:
    """更新当前用户资源。"""
    resource = await mydrive_resource_service.update(
        db,
        pk=pk,
        owner_id=request.user.id,
        updated_by=request.user.id,
        obj=obj,
    )
    return response_base.success(data=resource)


@router.delete('/{pk}', summary='删除资源', dependencies=[DependsJwtAuth])
async def delete_mydrive_resource(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='资源 ID')],
) -> ResponseModel:
    """删除当前用户资源。"""
    await mydrive_resource_service.delete(db, pk=pk, owner_id=request.user.id)
    return response_base.success()


@router.post('/{pk}/refresh-share', summary='刷新资源分享信息', dependencies=[DependsJwtAuth])
async def refresh_mydrive_resource_share(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='资源 ID')],
) -> ResponseSchemaModel[GetMyDriveResourceDetail]:
    """刷新当前用户资源分享信息。"""
    return response_base.success(data=await mydrive_resource_service.refresh_share_info(db, pk=pk, owner_id=request.user.id))


@router.post('/{pk}/rebuild-share', summary='重新创建资源分享', dependencies=[DependsJwtAuth])
async def rebuild_mydrive_resource_share(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='资源 ID')],
) -> ResponseSchemaModel[GetMyDriveResourceDetail]:
    """根据文件 ID 重新创建当前用户资源分享。"""
    return response_base.success(data=await mydrive_resource_service.rebuild_share(db, pk=pk, owner_id=request.user.id))


@router.post('/{pk}/cancel-share', summary='取消资源分享', dependencies=[DependsJwtAuth])
async def cancel_mydrive_resource_share(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='资源 ID')],
) -> ResponseSchemaModel[GetMyDriveResourceDetail]:
    """取消当前用户资源关联的个人分享链接。"""
    return response_base.success(data=await mydrive_resource_service.cancel_share(db, pk=pk, owner_id=request.user.id))


@router.post('/{pk}/view', summary='记录资源浏览', dependencies=[DependsJwtAuth])
async def record_mydrive_resource_view(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='资源 ID')],
) -> ResponseSchemaModel[GetMyDriveResourceDetail]:
    """记录当前用户资源浏览。"""
    return response_base.success(data=await mydrive_resource_service.record_view(db, pk=pk, owner_id=request.user.id))


@router.post('/{pk}/search-click', summary='记录资源搜索点击', dependencies=[DependsJwtAuth])
async def record_mydrive_resource_search_click(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='资源 ID')],
) -> ResponseSchemaModel[GetMyDriveResourceDetail]:
    """记录当前用户资源搜索点击。"""
    return response_base.success(data=await mydrive_resource_service.record_search_click(db, pk=pk, owner_id=request.user.id))


@router.get('/{pk}/view-trend', summary='获取资源浏览趋势', dependencies=[DependsJwtAuth, DependsPagination])
async def get_mydrive_resource_view_trend(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='资源 ID')],
    start_time: Annotated[datetime | None, Query(description='开始时间')] = None,
    end_time: Annotated[datetime | None, Query(description='结束时间')] = None,
) -> ResponseSchemaModel[PageData[GetMyDriveResourceViewHistoryDetail]]:
    """获取当前用户资源浏览趋势。"""
    params = GetMyDriveResourceViewTrendParam(start_time=start_time, end_time=end_time)
    return response_base.success(
        data=await mydrive_resource_service.get_view_trend(db, pk=pk, owner_id=request.user.id, params=params)
    )
