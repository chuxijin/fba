#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import Response

from backend.app.gongkao.schema.shiping import (
    CreateShipingParam,
    DeleteShipingParam,
    GetShipingDetail,
    ShipingParam,
    UpdateShipingParam,
)
from backend.app.gongkao.service import shiping_service, pdf_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取时评详情')
async def get_shiping(
    db: CurrentSession, pk: Annotated[int, Path(description='时评 ID')]
) -> ResponseSchemaModel[GetShipingDetail]:
    """获取时评详情"""
    data = await shiping_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='获取时评列表',
    dependencies=[DependsPagination],
)
async def get_shiping_list(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='标题')] = None,
    source: Annotated[str | None, Query(description='来源')] = None,
    author: Annotated[str | None, Query(description='作者')] = None,
    keywords: Annotated[str | None, Query(description='关键词')] = None,
    daily_date: Annotated[str | None, Query(description='每日时间')] = None,
) -> ResponseSchemaModel[PageData[GetShipingDetail]]:
    """获取时评列表（分页）"""
    from datetime import date as date_type

    params = ShipingParam(
        title=title,
        source=source,
        author=author,
        keywords=keywords,
        daily_date=date_type.fromisoformat(daily_date) if daily_date else None,
    )
    data = await shiping_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建时评',
    dependencies=[
        Depends(RequestPermission('gongkao:shiping:create')),
        DependsRBAC,
    ],
)
async def create_shiping(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateShipingParam,
) -> ResponseModel:
    """创建时评"""
    await shiping_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新时评',
    dependencies=[
        Depends(RequestPermission('gongkao:shiping:update')),
        DependsRBAC,
    ],
)
async def update_shiping(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='时评 ID')],
    obj: UpdateShipingParam,
) -> ResponseModel:
    """更新时评"""
    count = await shiping_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除时评',
    dependencies=[
        Depends(RequestPermission('gongkao:shiping:delete')),
        DependsRBAC,
    ],
)
async def delete_shiping(db: CurrentSessionTransaction, obj: DeleteShipingParam) -> ResponseModel:
    """删除时评"""
    count = await shiping_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post('/{pk}/view', summary='增加阅读量')
async def increment_shiping_view(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='时评 ID')]
) -> ResponseModel:
    """增加阅读量"""
    await shiping_service.increment_view(db=db, pk=pk)
    return response_base.success()


@router.get('/{pk}/pdf', summary='导出时评为PDF')
async def export_shiping_pdf(
    db: CurrentSession, pk: Annotated[int, Path(description='时评 ID')]
) -> Response:
    """导出时评为PDF文件"""
    shiping = await shiping_service.get(db=db, pk=pk)
    pdf_bytes = await pdf_service.export_pdf(shiping)

    filename = f"{shiping.title}_{shiping.daily_date or 'shiping'}.pdf"
    # 对文件名进行 URL 编码以支持中文
    from urllib.parse import quote
    encoded_filename = quote(filename)

    return Response(
        content=pdf_bytes,
        media_type='application/pdf',
        headers={
            'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )
