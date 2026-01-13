#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.gongkao.schema.ciyu import (
    CreateCiyuParam,
    DeleteCiyuParam,
    GetCiyuDetail,
    CiyuParam,
    UpdateCiyuParam,
)
from backend.app.gongkao.service.ciyu_service import ciyu_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取词语详情')
async def get_ciyu(
    db: CurrentSession, pk: Annotated[int, Path(description='词语 ID')]
) -> ResponseSchemaModel[GetCiyuDetail]:
    """获取词语详情"""
    data = await ciyu_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取词语列表')
async def get_ciyu_list(
    db: CurrentSession,
    word: Annotated[str | None, Query(description='词语')] = None,
    category: Annotated[str | None, Query(description='分类')] = None,
    emotion: Annotated[str | None, Query(description='感情色彩')] = None,
    frequency: Annotated[int | None, Query(description='考频')] = None,
) -> ResponseSchemaModel[list[GetCiyuDetail]]:
    """获取词语列表"""
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
    db: CurrentSessionTransaction,
    obj: CreateCiyuParam,
    user_id: Annotated[int, DependsJwtAuth],
) -> ResponseModel:
    """创建词语"""
    await ciyu_service.create(db=db, obj=obj, created_by=user_id)
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
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='词语 ID')],
    obj: UpdateCiyuParam,
    user_id: Annotated[int, DependsJwtAuth],
) -> ResponseModel:
    """更新词语"""
    count = await ciyu_service.update(db=db, pk=pk, obj=obj, updated_by=user_id)
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
