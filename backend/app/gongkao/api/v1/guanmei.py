#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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


@router.get('/{pk}', summary='获取官媒学言语详情')
async def get_guanmei(
    db: CurrentSession,
    pk: Annotated[int, Path(description='ID')],
) -> ResponseSchemaModel[GetContentDetail]:
    """获取官媒学言语详情"""
    data = await content_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取官媒学言语列表', dependencies=[DependsPagination])
async def get_guanmei_list(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='标题')] = None,
    category_id: Annotated[int | None, Query(description='分类 ID')] = None,
    tag: Annotated[str | None, Query(description='标签')] = None,
    daily_date: Annotated[str | None, Query(description='日期')] = None,
) -> ResponseSchemaModel[PageData[GetContentListDetail]]:
    """获取官媒学言语列表（分页），只返回已发布内容"""
    params = ContentParam(
        title=title,
        category_id=category_id,
        tag=tag,
        is_published=True,
        daily_date=date_type.fromisoformat(daily_date) if daily_date else None,
    )
    data = await content_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post('/{pk}/view', summary='增加官媒学言语阅读量')
async def increment_guanmei_view(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='ID')],
) -> ResponseModel:
    """增加官媒学言语阅读量"""
    await content_service.increment_view(db=db, pk=pk)
    return response_base.success()
