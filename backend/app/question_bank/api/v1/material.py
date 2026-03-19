#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""材料管理 API 路由"""
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.question_bank.schema.material import (
    CreateMaterialParam,
    DeleteMaterialParam,
    GetMaterialDetail,
    GetMaterialListItem,
    GetMaterialWithRelationDetail,
    LinkQuestionParam,
    MaterialParam,
    UpdateMaterialParam,
)
from backend.app.question_bank.service.material_service import material_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取材料详情', name='qbank_get_material')
async def get_material(
    db: CurrentSession,
    pk: Annotated[int, Path(description='材料 ID')],
) -> ResponseSchemaModel[GetMaterialWithRelationDetail]:
    """🔐 管理员接口 - 获取材料详情（包含关联信息）"""
    data = await material_service.get_with_relation(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取材料列表', name='qbank_get_material_list', dependencies=[DependsRBAC])
async def get_material_list(
    db: CurrentSession,
    bank_id: Annotated[int | None, Query(description='题库 ID')] = None,
    category_id: Annotated[int | None, Query(description='分类 ID')] = None,
    keyword: Annotated[str | None, Query(description='关键字搜索')] = None,
    is_active: Annotated[bool | None, Query(description='是否启用')] = None,
    year: Annotated[int | None, Query(description='年份')] = None,
) -> ResponseSchemaModel[list[GetMaterialListItem]]:
    """🔐 管理员接口 - 获取材料列表"""
    params = MaterialParam(
        bank_id=bank_id,
        category_id=category_id,
        keyword=keyword,
        is_active=is_active,
        year=year,
    )
    data = await material_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.get('/bank/{bank_id}', summary='获取题库材料列表', name='qbank_get_material_by_bank')
async def get_material_by_bank(
    db: CurrentSession,
    bank_id: Annotated[int, Path(description='题库 ID')],
    is_active: Annotated[bool | None, Query(description='是否启用')] = None,
) -> ResponseSchemaModel[list[GetMaterialListItem]]:
    """🔐 管理员接口 - 获取指定题库的材料列表"""
    data = await material_service.get_by_bank(db=db, bank_id=bank_id, is_active=is_active)
    return response_base.success(data=data)


@router.post('', summary='创建材料', name='qbank_create_material', dependencies=[DependsRBAC])
async def create_material(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateMaterialParam,
) -> ResponseSchemaModel[GetMaterialDetail]:
    """🔐 管理员接口 - 创建材料"""
    material = await material_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=material)


@router.put('/{pk}', summary='更新材料', name='qbank_update_material', dependencies=[DependsRBAC])
async def update_material(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='材料 ID')],
    obj: UpdateMaterialParam,
) -> ResponseModel:
    """🔐 管理员接口 - 更新材料"""
    count = await material_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('', summary='删除材料', name='qbank_delete_material', dependencies=[DependsRBAC])
async def delete_material(
    db: CurrentSessionTransaction,
    obj: DeleteMaterialParam,
) -> ResponseModel:
    """🔐 管理员接口 - 批量删除材料"""
    count = await material_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post('/{pk}/link', summary='关联题目', name='qbank_link_material_questions', dependencies=[DependsRBAC])
async def link_questions(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='材料 ID')],
    obj: LinkQuestionParam,
) -> ResponseModel:
    """🔐 管理员接口 - 将题目关联到材料"""
    await material_service.link_questions(db=db, pk=pk, obj=obj)
    return response_base.success()


@router.post('/{pk}/unlink', summary='解除关联', name='qbank_unlink_material_questions', dependencies=[DependsRBAC])
async def unlink_questions(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='材料 ID')],
    obj: LinkQuestionParam,
) -> ResponseModel:
    """🔐 管理员接口 - 解除题目与材料的关联"""
    count = await material_service.unlink_questions(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()

