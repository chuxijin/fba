#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.content.schema.content import (
    GetContentDetail,
)
from backend.app.content.schema.content import (
    GetContentListDetails as GetContentListDetail,
)
from backend.app.content.service.content_service import content_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

router = APIRouter()


@router.get('/{pk}', summary='获取经验详情', response_model=ResponseSchemaModel[GetContentDetail])
async def get_jingyan(
    db: CurrentSession,
    pk: Annotated[int, Path(description='内容 ID')],
):
    data = await content_service.get_with_incr_view(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取经验列表', response_model=ResponseSchemaModel[list[GetContentListDetail]])
async def get_jingyan_list(
    db: CurrentSession,
    app_code: Annotated[str, Query(description='应用标识')] = 'gongkao',
    category_id: Annotated[int, Query(description='分类 ID')] = 33,
    is_published: Annotated[bool, Query(description='是否发布')] = True,
):
    contents = await content_service.get_list(
        db=db, 
        app_code=app_code, 
        category_id=category_id, 
        is_published=is_published
    )
    return response_base.success(data=contents)
