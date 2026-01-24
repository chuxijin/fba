#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.gongkao.schema.ciyu import (
    CreateCiyuParam,
    DeleteCiyuParam,
    GetCiyuDetail,
    CiyuParam,
    UpdateCiyuParam,
)
from backend.app.gongkao.service.ciyu_service import ciyu_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/hot', summary='获取热门词语')
async def get_hot_ciyu(
    db: CurrentSession,
    limit: Annotated[int, Query(description='返回数量', ge=1, le=50)] = 10,
) -> ResponseSchemaModel[list[GetCiyuDetail]]:
    """获取热门词语（按浏览量排序）"""
    data = await ciyu_service.get_hot(db=db, limit=limit)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取词语详情')
async def get_ciyu(
    db: CurrentSession, pk: Annotated[int, Path(description='词语 ID')]
) -> ResponseSchemaModel[GetCiyuDetail]:
    """获取词语详情"""
    data = await ciyu_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='获取词语列表',
    dependencies=[DependsPagination],
)
async def get_ciyu_list(
    db: CurrentSession,
    word: Annotated[str | None, Query(description='词语')] = None,
    category: Annotated[str | None, Query(description='分类')] = None,
    emotion: Annotated[str | None, Query(description='感情色彩')] = None,
    frequency: Annotated[int | None, Query(description='考频')] = None,
) -> ResponseSchemaModel[PageData[GetCiyuDetail]]:
    """获取词语列表（分页）"""
    params = CiyuParam(word=word, category=category, emotion=emotion, frequency=frequency)
    data = await ciyu_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建词语',
    dependencies=[
        Depends(RequestPermission('gongkao:ciyu:create')),
        DependsRBAC,
    ],
)
async def create_ciyu(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateCiyuParam,
) -> ResponseModel:
    """创建词语"""
    await ciyu_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新词语',
    dependencies=[
        Depends(RequestPermission('gongkao:ciyu:update')),
        DependsRBAC,
    ],
)
async def update_ciyu(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='词语 ID')],
    obj: UpdateCiyuParam,
) -> ResponseModel:
    """更新词语"""
    count = await ciyu_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除词语',
    dependencies=[
        Depends(RequestPermission('gongkao:ciyu:delete')),
        DependsRBAC,
    ],
)
async def delete_ciyu(db: CurrentSessionTransaction, obj: DeleteCiyuParam) -> ResponseModel:
    """删除词语"""
    count = await ciyu_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post('/{pk}/view', summary='增加词语阅读量')
async def increment_ciyu_view(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='词语 ID')],
) -> ResponseModel:
    """增加词语阅读量"""
    count = await ciyu_service.increment_view(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
