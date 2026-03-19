#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.gongkao.schema.hanyu import (
    CreateHanyuParam,
    DeleteHanyuParam,
    GetHanyuDetail,
    GetHanyuListDetail,
    HanyuParam,
    UpdateHanyuParam,
)
from backend.app.gongkao.service.hanyu_service import hanyu_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/types', summary='获取汉语词汇类型')
async def get_hanyu_types(db: CurrentSession) -> ResponseSchemaModel[list[str]]:
    """获取所有汉语词汇类型"""
    data = await hanyu_service.get_types(db=db)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取汉语词汇详情')
async def get_hanyu(
    db: CurrentSession,
    pk: Annotated[int, Path(description='id')],
) -> ResponseSchemaModel[GetHanyuDetail]:
    """根据 ID 获取汉语词汇详情"""
    data = await hanyu_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('/name/{name}', summary='根据名称获取汉语词汇')
async def get_hanyu_by_name(
    db: CurrentSession,
    name: Annotated[str, Path(description='词语名称')],
    type_: Annotated[str | None, Query(alias='type', description='类型')] = None,
) -> ResponseSchemaModel[GetHanyuDetail]:
    """根据名称获取汉语词汇详情"""
    data = await hanyu_service.get_by_name(db=db, name=name, type_=type_)
    return response_base.success(data=data)


@router.get('', summary='获取汉语词汇列表', dependencies=[DependsPagination])
async def get_hanyu_list(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='词语名称关键字')] = None,
    type_: Annotated[str | None, Query(alias='type', description='类型')] = None,
    baobian: Annotated[str | None, Query(description='褒贬色彩')] = None,
    structure: Annotated[str | None, Query(description='结构')] = None,
    min_frequency: Annotated[int | None, Query(description='最小使用频次')] = None,
) -> ResponseSchemaModel[PageData[GetHanyuListDetail]]:
    """获取汉语词汇列表（分页）"""
    params = HanyuParam(
        name=name,
        type=type_,
        baobian=baobian,
        structure=structure,
        min_frequency=min_frequency,
    )
    data = await hanyu_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建汉语词汇',
    dependencies=[Depends(RequestPermission('gongkao:hanyu:create')), DependsRBAC],
)
async def create_hanyu(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateHanyuParam,
) -> ResponseModel:
    """创建汉语词汇"""
    await hanyu_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新汉语词汇',
    dependencies=[Depends(RequestPermission('gongkao:hanyu:update')), DependsRBAC],
)
async def update_hanyu(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='id')],
    obj: UpdateHanyuParam,
) -> ResponseModel:
    """更新汉语词汇"""
    count = await hanyu_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除汉语词汇',
    dependencies=[Depends(RequestPermission('gongkao:hanyu:delete')), DependsRBAC],
)
async def delete_hanyu(db: CurrentSessionTransaction, obj: DeleteHanyuParam) -> ResponseModel:
    """删除汉语词汇"""
    count = await hanyu_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post('/{pk}/frequency', summary='增加汉语词汇使用频次')
async def increment_hanyu_frequency(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='id')],
) -> ResponseModel:
    """增加汉语词汇使用频次"""
    await hanyu_service.increment_frequency(db=db, pk=pk)
    return response_base.success()
