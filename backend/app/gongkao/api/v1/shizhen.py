#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.gongkao.schema.shizhen import GetShizhenDetail, GetShizhenListDetail
from backend.app.gongkao.service.shizhen_service import shizhen_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

router = APIRouter()


@router.get(
    '',
    summary='获取时政列表',
    response_model=ResponseSchemaModel[PageData[GetShizhenListDetail]],
    dependencies=[DependsPagination],
)
async def get_shizhen_list(
    db: CurrentSession,
    daily_date: Annotated[str | None, Query(description='按日期筛选，格式 YYYY-MM-DD')] = None,
):
    page_data = await shizhen_service.get_list_paged(db=db, daily_date=daily_date)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取时政详情', response_model=ResponseSchemaModel[GetShizhenDetail])
async def get_shizhen(
    db: CurrentSession,
    pk: Annotated[int, Path(description='时政 ID')],
):
    data = await shizhen_service.get_with_incr_view(db=db, pk=pk)
    return response_base.success(data=data)
