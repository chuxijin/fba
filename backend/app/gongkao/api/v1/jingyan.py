#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经验模块 - 基于 content 的封装接口"""
from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.gongkao.schema.content import (
    ContentParam,
    GetContentDetail,
    GetContentListDetail,
)
from backend.app.gongkao.service.content_service import content_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='Get jingyan detail')
async def get_jingyan(
    db: CurrentSession,
    pk: Annotated[int, Path(description='id')],
) -> ResponseSchemaModel[GetContentDetail]:
    """Get jingyan detail by id."""
    data = await content_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='Get jingyan list', dependencies=[DependsPagination])
async def get_jingyan_list(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='title keyword')] = None,
    category_id: Annotated[int, Query(description='分类 ID')] = 33,
    tag: Annotated[str | None, Query(description='tag')] = None,
    daily_date: Annotated[str | None, Query(description='daily date')] = None,
) -> ResponseSchemaModel[PageData[GetContentListDetail]]:
    """获取经验列表（分页），默认分类 ID=33，可传子分类 ID 进一步筛选"""
    params = ContentParam(
        title=title,
        category_id=category_id,
        tag=tag,
        is_published=True,
        daily_date=date_type.fromisoformat(daily_date) if daily_date else None,
    )
    data = await content_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post('/{pk}/view', summary='Increment jingyan view count')
async def increment_jingyan_view(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='id')],
) -> ResponseModel:
    """Increment jingyan view count."""
    await content_service.increment_view(db=db, pk=pk)
    return response_base.success()
