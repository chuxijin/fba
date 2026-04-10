#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.content.schema.content import (
    GetContentDetail,
    GetContentListDetails as GetContentListDetail,
)
from backend.app.content.service.content_service import content_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('/{pk}', summary='获取时评详情', response_model=ResponseSchemaModel[GetContentDetail])
async def get_shiping(
    db: CurrentSession,
    pk: Annotated[int, Path(description='内容 ID')],
):
    data = await content_service.get_with_incr_view(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取时评列表', response_model=ResponseSchemaModel[list[GetContentListDetail]])
async def get_shiping_list(
    db: CurrentSession,
    app_code: str = Query('gongkao', description='应用标识'),
    category_id: int = Query(34, description='分类 ID'),
    is_published: bool = Query(True, description='是否发布'),
):
    contents = await content_service.get_list(
        db=db, 
        app_code=app_code, 
        category_id=category_id, 
        is_published=is_published
    )
    return response_base.success(data=contents)
