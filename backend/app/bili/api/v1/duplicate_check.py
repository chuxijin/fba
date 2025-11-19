#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.bili.crud import bili_duplicate_check_dao
from backend.app.bili.schema.duplicate_check import (
    CreateBiliDuplicateCheckParam,
    GetBiliDuplicateCheckDetail,
    UpdateBiliDuplicateCheckParam,
)
from backend.app.bili.service import bili_duplicate_check_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取 B 站操作记录详情')
async def get_bili_duplicate_check(
    db: CurrentSession, pk: Annotated[int, Path(description='记录 ID')]
) -> ResponseSchemaModel[GetBiliDuplicateCheckDetail]:
    """获取 B 站操作记录详情"""
    data = await bili_duplicate_check_service.get(db, pk)
    return response_base.success(data=data)


@router.get('', summary='分页获取 B 站操作记录列表', dependencies=[DependsPagination])
async def get_bili_duplicate_check_list(
    db: CurrentSession,
    mid: Annotated[str | None, Query(description='用户 MID')] = None,
    operation_type: Annotated[str | None, Query(description='操作类型')] = None,
    is_active: Annotated[bool | None, Query(description='是否主动')] = None,
    work_id: Annotated[int | None, Query(description='作品 ID')] = None,
    execution_log_id: Annotated[int | None, Query(description='任务执行记录 ID')] = None,
) -> ResponseSchemaModel[PageData[GetBiliDuplicateCheckDetail]]:
    """分页获取 B 站操作记录列表"""
    page_data = await bili_duplicate_check_service.get_list(
        db=db, mid=mid, operation_type=operation_type, is_active=is_active, work_id=work_id, execution_log_id=execution_log_id
    )
    return response_base.success(data=page_data)


@router.post('', summary='创建 B 站操作记录')
async def create_bili_duplicate_check(db: CurrentSessionTransaction, obj: CreateBiliDuplicateCheckParam) -> ResponseModel:
    """创建 B 站操作记录"""
    await bili_duplicate_check_service.create(db, obj)
    return response_base.success()


@router.put('/{pk}', summary='更新 B 站操作记录')
async def update_bili_duplicate_check(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='记录 ID')], obj: UpdateBiliDuplicateCheckParam
) -> ResponseModel:
    """更新 B 站操作记录"""
    count = await bili_duplicate_check_service.update(db, pk, obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除 B 站操作记录')
async def delete_bili_duplicate_check(db: CurrentSessionTransaction, pk: Annotated[int, Path(description='记录 ID')]) -> ResponseModel:
    """删除 B 站操作记录"""
    count = await bili_duplicate_check_service.delete(db, pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
