#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.content.schema.content import (
    GetContentDetail,
    GetContentListDetails as GetContentListDetail,
)
from backend.app.content.service.content_service import content_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('/{pk}', summary='获取时政详情', response_model=ResponseSchemaModel[GetContentDetail])
async def get_shizhen(
    db: CurrentSession,
    pk: Annotated[int, Path(description='时政 ID')],
):
    """获取时政详情"""
    # 强制加上 app_code 逻辑
    data = await content_service.get_with_incr_view(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取时政列表', response_model=ResponseSchemaModel[list[GetContentListDetail]])
async def get_shizhen_list(
    db: CurrentSession,
    app_code: str = Query('gongkao', description='应用标识'),
    category_id: int = Query(32, description='分类 ID'),
    is_published: bool = Query(True, description='是否发布'),
):
    """获取时政列表，默认分类 ID=32 (时政)"""
    contents = await content_service.get_list(
        db=db, 
        app_code=app_code, 
        category_id=category_id, 
        is_published=is_published
    )
    return response_base.success(data=contents)
