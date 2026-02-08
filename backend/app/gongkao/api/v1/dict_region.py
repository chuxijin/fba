#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.gongkao.schema.dict_region import (
    CreateDictRegionParam,
    DictRegionParam,
    GetDictRegionDetail,
    UpdateDictRegionParam,
)
from backend.app.gongkao.service.dict_region_service import dict_region_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/tree',
    summary='获取地区树',
    dependencies=[DependsJwtAuth],
)
async def get_dict_region_tree(db: CurrentSession) -> ResponseSchemaModel[list]:
    """获取地区树形结构"""
    data = await dict_region_service.get_tree(db=db)
    return response_base.success(data=data)


@router.get(
    '/provinces',
    summary='获取省份列表',
    dependencies=[DependsJwtAuth],
)
async def get_dict_region_provinces(db: CurrentSession) -> ResponseSchemaModel[list[GetDictRegionDetail]]:
    """获取所有省份"""
    data = await dict_region_service.get_provinces(db=db)
    return response_base.success(data=data)


@router.get(
    '/children',
    summary='获取子地区',
    dependencies=[DependsJwtAuth],
)
async def get_dict_region_children(
    db: CurrentSession,
    parent_code: Annotated[str | None, Query(description='父级代码')] = None,
) -> ResponseSchemaModel[list[GetDictRegionDetail]]:
    """获取子地区列表"""
    data = await dict_region_service.get_children(db=db, parent_code=parent_code)
    return response_base.success(data=data)


@router.get(
    '/{pk}',
    summary='获取地区详情',
    dependencies=[DependsJwtAuth],
)
async def get_dict_region(
    db: CurrentSession,
    pk: Annotated[int, Path(description='地区 ID')],
) -> ResponseSchemaModel[GetDictRegionDetail]:
    """获取地区详情"""
    data = await dict_region_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '/code/{code}',
    summary='通过代码获取地区',
    dependencies=[DependsJwtAuth],
)
async def get_dict_region_by_code(
    db: CurrentSession,
    code: Annotated[str, Path(description='地区代码')],
) -> ResponseSchemaModel[GetDictRegionDetail]:
    """通过地区代码获取"""
    data = await dict_region_service.get_by_code(db=db, code=code)
    return response_base.success(data=data)


@router.get(
    '',
    summary='获取地区列表',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_dict_region_list(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='地区名称')] = None,
    level: Annotated[int | None, Query(description='级别')] = None,
    parent_code: Annotated[str | None, Query(description='父级代码')] = None,
) -> ResponseSchemaModel[PageData[GetDictRegionDetail]]:
    """获取地区列表（分页）"""
    params = DictRegionParam(name=name, level=level, parent_code=parent_code)
    data = await dict_region_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建地区',
    dependencies=[
        Depends(RequestPermission('gongkao:dict:region:create')),
        DependsRBAC,
    ],
)
async def create_dict_region(
    db: CurrentSessionTransaction,
    obj: CreateDictRegionParam,
) -> ResponseModel:
    """创建地区"""
    await dict_region_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新地区',
    dependencies=[
        Depends(RequestPermission('gongkao:dict:region:update')),
        DependsRBAC,
    ],
)
async def update_dict_region(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='地区 ID')],
    obj: UpdateDictRegionParam,
) -> ResponseModel:
    """更新地区"""
    count = await dict_region_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/{pk}',
    summary='删除地区',
    dependencies=[
        Depends(RequestPermission('gongkao:dict:region:delete')),
        DependsRBAC,
    ],
)
async def delete_dict_region(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='地区 ID')],
) -> ResponseModel:
    """删除地区"""
    count = await dict_region_service.delete(db=db, pks=[pk])
    if count > 0:
        return response_base.success()
    return response_base.fail()
