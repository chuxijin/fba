#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.bili.crud import bili_category_dao
from backend.app.bili.schema.category import (
    CreateBiliCategoryParam,
    GetBiliCategoryDetail,
    GetBiliCategoryTree,
    UpdateBiliCategoryParam,
)
from backend.app.bili.service import bili_category_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/tree', summary='获取 B 站分类树')
async def get_bili_category_tree(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='分类名称')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[list[GetBiliCategoryTree]]:
    """获取 B 站分类树形结构"""
    data = await bili_category_service.get_tree(db, name=name, status=status)
    return response_base.success(data=data)


@router.get('', summary='获取 B 站分类列表')
async def get_bili_category_list(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='分类名称')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
    parent_id: Annotated[int | None, Query(description='父分类 ID')] = None,
) -> ResponseSchemaModel[list[GetBiliCategoryDetail]]:
    """获取 B 站分类列表"""
    data = await bili_category_dao.get_list(db, name=name, status=status, parent_id=parent_id)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取 B 站分类详情')
async def get_bili_category(
    db: CurrentSession, pk: Annotated[int, Path(description='分类 ID')]
) -> ResponseSchemaModel[GetBiliCategoryDetail]:
    """获取 B 站分类详情"""
    data = await bili_category_service.get(db, pk)
    return response_base.success(data=data)


@router.post('', summary='创建 B 站分类')
async def create_bili_category(db: CurrentSessionTransaction, obj: CreateBiliCategoryParam) -> ResponseModel:
    """创建 B 站分类"""
    await bili_category_service.create(db, obj)
    return response_base.success()


@router.put('/{pk}', summary='更新 B 站分类')
async def update_bili_category(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='分类 ID')], obj: UpdateBiliCategoryParam
) -> ResponseModel:
    """更新 B 站分类"""
    count = await bili_category_service.update(db, pk, obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除 B 站分类')
async def delete_bili_category(db: CurrentSessionTransaction, pk: Annotated[int, Path(description='分类 ID')]) -> ResponseModel:
    """删除 B 站分类"""
    count = await bili_category_service.delete(db, pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
