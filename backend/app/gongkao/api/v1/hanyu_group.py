#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.gongkao.schema.hanyu_group import (
    CreateHanyuGroupParam,
    DeleteHanyuGroupParam,
    GetHanyuGroupDetail,
    GetHanyuGroupListDetail,
    HanyuGroupParam,
    UpdateHanyuGroupParam,
)
from backend.app.gongkao.service.hanyu_group_service import hanyu_group_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/categories', summary='获取辨析组分类列表')
async def get_hanyu_group_categories(db: CurrentSession) -> ResponseSchemaModel[list[str]]:
    """获取所有辨析组分类"""
    data = await hanyu_group_service.get_categories(db=db)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取辨析组详情')
async def get_hanyu_group(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='id')],
) -> ResponseSchemaModel[GetHanyuGroupDetail]:
    """根据 ID 获取辨析组详情（含成员明细）"""
    data = await hanyu_group_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取辨析组列表', dependencies=[DependsPagination])
async def get_hanyu_group_list(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='标题关键字')] = None,
    category: Annotated[str | None, Query(description='分类')] = None,
    group_no: Annotated[str | None, Query(description='序号/题号')] = None,
) -> ResponseSchemaModel[PageData[GetHanyuGroupListDetail]]:
    """获取辨析组列表（分页）"""
    params = HanyuGroupParam(title=title, category=category, group_no=group_no)
    data = await hanyu_group_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建辨析组',
    dependencies=[Depends(RequestPermission('gongkao:hanyu_group:create')), DependsRBAC],
)
async def create_hanyu_group(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateHanyuGroupParam,
) -> ResponseModel:
    """创建辨析组（含成员明细）"""
    await hanyu_group_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新辨析组',
    dependencies=[Depends(RequestPermission('gongkao:hanyu_group:update')), DependsRBAC],
)
async def update_hanyu_group(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='id')],
    obj: UpdateHanyuGroupParam,
) -> ResponseModel:
    """更新辨析组（items 传入则整体替换成员明细）"""
    await hanyu_group_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    return response_base.success()


@router.delete(
    '',
    summary='删除辨析组',
    dependencies=[Depends(RequestPermission('gongkao:hanyu_group:delete')), DependsRBAC],
)
async def delete_hanyu_group(db: CurrentSessionTransaction, obj: DeleteHanyuGroupParam) -> ResponseModel:
    """删除辨析组（级联删除成员明细）"""
    count = await hanyu_group_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
