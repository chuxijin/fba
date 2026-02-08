#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.gongkao.schema.dict_major import (
    CreateDictMajorParam,
    DictMajorParam,
    GetDictMajorDetail,
    MajorMatchResult,
    UpdateDictMajorParam,
)
from backend.app.gongkao.service.dict_major_service import dict_major_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/tree',
    summary='获取专业树',
    dependencies=[DependsJwtAuth],
)
async def get_dict_major_tree(
    db: CurrentSession,
    edu_level: Annotated[str | None, Query(description='学历层次')] = None,
) -> ResponseSchemaModel[list]:
    """获取专业树形结构"""
    data = await dict_major_service.get_tree(db=db, edu_level=edu_level)
    return response_base.success(data=data)


@router.get(
    '/children',
    summary='获取子专业',
    dependencies=[DependsJwtAuth],
)
async def get_dict_major_children(
    db: CurrentSession,
    parent_code: Annotated[str | None, Query(description='父级代码')] = None,
) -> ResponseSchemaModel[list[GetDictMajorDetail]]:
    """获取子专业列表"""
    data = await dict_major_service.get_children(db=db, parent_code=parent_code)
    return response_base.success(data=data)


@router.get(
    '/search',
    summary='搜索专业',
    dependencies=[DependsJwtAuth],
)
async def search_dict_major(
    db: CurrentSession,
    keyword: Annotated[str, Query(description='搜索关键词')],
    edu_level: Annotated[str | None, Query(description='学历层次')] = None,
) -> ResponseSchemaModel[list[GetDictMajorDetail]]:
    """搜索专业（名称或别名）"""
    data = await dict_major_service.search(db=db, keyword=keyword, edu_level=edu_level)
    return response_base.success(data=data)


@router.get(
    '/match',
    summary='匹配专业',
    dependencies=[DependsJwtAuth],
)
async def match_dict_major(
    db: CurrentSession,
    major_name: Annotated[str, Query(description='专业名称')],
    edu_level: Annotated[str, Query(description='学历层次')] = '本科',
) -> ResponseSchemaModel[MajorMatchResult | None]:
    """匹配专业（返回匹配结果和匹配类型）"""
    data = await dict_major_service.match_major(db=db, major_name=major_name, edu_level=edu_level)
    return response_base.success(data=data)


@router.get(
    '/{pk}',
    summary='获取专业详情',
    dependencies=[DependsJwtAuth],
)
async def get_dict_major(
    db: CurrentSession,
    pk: Annotated[int, Path(description='专业 ID')],
) -> ResponseSchemaModel[GetDictMajorDetail]:
    """获取专业详情"""
    data = await dict_major_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '/code/{code}',
    summary='通过代码获取专业',
    dependencies=[DependsJwtAuth],
)
async def get_dict_major_by_code(
    db: CurrentSession,
    code: Annotated[str, Path(description='专业代码')],
) -> ResponseSchemaModel[GetDictMajorDetail]:
    """通过专业代码获取"""
    data = await dict_major_service.get_by_code(db=db, code=code)
    return response_base.success(data=data)


@router.get(
    '',
    summary='获取专业列表',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_dict_major_list(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='专业名称')] = None,
    level: Annotated[int | None, Query(description='级别')] = None,
    parent_code: Annotated[str | None, Query(description='父级代码')] = None,
    edu_level: Annotated[str | None, Query(description='学历层次')] = None,
    is_active: Annotated[bool | None, Query(description='是否启用')] = None,
) -> ResponseSchemaModel[PageData[GetDictMajorDetail]]:
    """获取专业列表（分页）"""
    params = DictMajorParam(
        name=name,
        level=level,
        parent_code=parent_code,
        edu_level=edu_level,
        is_active=is_active,
    )
    data = await dict_major_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建专业',
    dependencies=[
        Depends(RequestPermission('gongkao:dict:major:create')),
        DependsRBAC,
    ],
)
async def create_dict_major(
    db: CurrentSessionTransaction,
    obj: CreateDictMajorParam,
) -> ResponseModel:
    """创建专业"""
    await dict_major_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新专业',
    dependencies=[
        Depends(RequestPermission('gongkao:dict:major:update')),
        DependsRBAC,
    ],
)
async def update_dict_major(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='专业 ID')],
    obj: UpdateDictMajorParam,
) -> ResponseModel:
    """更新专业"""
    count = await dict_major_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/{pk}',
    summary='删除专业',
    dependencies=[
        Depends(RequestPermission('gongkao:dict:major:delete')),
        DependsRBAC,
    ],
)
async def delete_dict_major(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='专业 ID')],
) -> ResponseModel:
    """删除专业"""
    count = await dict_major_service.delete(db=db, pks=[pk])
    if count > 0:
        return response_base.success()
    return response_base.fail()
