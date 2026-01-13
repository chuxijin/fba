#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.question_bank.schema.bank import (
    CreateBankParam,
    DeleteBankParam,
    GetBankDetail,
    GetBankDetailWithChapters,
    UpdateBankParam,
)
from backend.app.question_bank.service.bank_service import bank_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/recommend', summary='获取推荐题库', name='qbank_get_recommend_banks')
async def get_recommend_banks(
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetBankDetail]]:
    """🌍 公开接口 - 获取全局热门推荐题库（最近7天做题最多的前5个）"""
    data = await bank_service.get_recommend_banks(db=db)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取题库详情', name='qbank_get_bank')
async def get_bank(
    db: CurrentSession, pk: Annotated[int, Path(description='题库 ID')]
) -> ResponseSchemaModel[GetBankDetailWithChapters]:
    """🌍 公开接口 - 任何人都可以查看题库详情（含章节树）"""
    data = await bank_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取题库树形列表', name='qbank_get_bank_list')
async def get_bank_list(
    db: CurrentSession,
    cat_id: Annotated[int | None, Query(description='分类 ID')] = None,
    status: Annotated[int | None, Query(description='题库状态')] = None,
    scope: Annotated[int | None, Query(description='可见范围')] = None,
    keyword: Annotated[str | None, Query(description='关键字搜索')] = None,
) -> ResponseModel:
    """🌍 公开接口 - 任何人都可以查看题库树形列表"""
    data = await bank_service.get_list(db=db, cat_id=cat_id, status=status, scope=scope, keyword=keyword)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建题库',
    name='qbank_create_bank',
    dependencies=[
        Depends(RequestPermission('question_bank:bank:create')),
        DependsRBAC,
    ],
)
async def create_bank(db: CurrentSessionTransaction, obj: CreateBankParam) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以创建题库"""
    await bank_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新题库',
    name='qbank_update_bank',
    dependencies=[
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
    ],
)
async def update_bank(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='题库 ID')], obj: UpdateBankParam
) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以更新题库"""
    count = await bank_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除题库',
    name='qbank_delete_bank',
    dependencies=[
        Depends(RequestPermission('question_bank:bank:delete')),
        DependsRBAC,
    ],
)
async def delete_bank(db: CurrentSessionTransaction, obj: DeleteBankParam) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以删除题库"""
    count = await bank_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
