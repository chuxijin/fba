#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.bili.crud import bili_account_dao
from backend.app.bili.schema.account import CreateBiliAccountParam, GetBiliAccountDetail, UpdateBiliAccountParam
from backend.app.bili.service import bili_account_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('', summary='获取 B 站账号列表')
async def get_bili_account_list(
    db: CurrentSession,
    account_name: Annotated[str | None, Query(description='账号名称')] = None,
    mid: Annotated[str | None, Query(description='B 站用户 MID')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
    category_id: Annotated[int | None, Query(description='分类 ID')] = None,
) -> ResponseSchemaModel[list[GetBiliAccountDetail]]:
    """获取 B 站账号列表"""
    data = await bili_account_dao.get_list(db, account_name=account_name, mid=mid, status=status, category_id=category_id)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取 B 站账号详情')
async def get_bili_account(
    db: CurrentSession, pk: Annotated[int, Path(description='账号 ID')]
) -> ResponseSchemaModel[GetBiliAccountDetail]:
    """获取 B 站账号详情"""
    data = await bili_account_service.get(db, pk)
    return response_base.success(data=data)


@router.post('', summary='创建 B 站账号')
async def create_bili_account(db: CurrentSessionTransaction, obj: CreateBiliAccountParam) -> ResponseModel:
    """创建 B 站账号"""
    await bili_account_service.create(db, obj)
    return response_base.success()


@router.put('/{pk}', summary='更新 B 站账号')
async def update_bili_account(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='账号 ID')], obj: UpdateBiliAccountParam
) -> ResponseModel:
    """更新 B 站账号"""
    count = await bili_account_service.update(db, pk, obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除 B 站账号')
async def delete_bili_account(db: CurrentSessionTransaction, pk: Annotated[int, Path(description='账号 ID')]) -> ResponseModel:
    """删除 B 站账号"""
    count = await bili_account_service.delete(db, pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
