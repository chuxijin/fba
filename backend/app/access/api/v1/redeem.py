#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.access.schema.redeem import (
    AgisoBatchRuleParam,
    CreateRedeemBatchParam,
    GetRedeemBatchDetail,
    SetAgisoBatchRulesParam,
    UpdateRedeemBatchParam,
)
from backend.app.access.service.redeem_service import access_redeem_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/batches/{pk}',
    summary='获取兑换批次详情',
    dependencies=[DependsJwtAuth],
)
async def get_redeem_batch(
    db: CurrentSession,
    pk: Annotated[int, Path(description='批次 ID')],
) -> ResponseSchemaModel[GetRedeemBatchDetail]:
    """获取兑换批次详情"""
    data = await access_redeem_service.get_batch(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '/batches',
    summary='分页获取兑换批次',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_redeem_batch_list(
    db: CurrentSession,
    app_id: Annotated[str | None, Query(description='应用 ID')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
    batch_no: Annotated[str | None, Query(description='批次编号')] = None,
) -> ResponseSchemaModel[PageData[GetRedeemBatchDetail]]:
    """分页获取兑换批次"""
    page_data = await access_redeem_service.get_batch_list(
        db=db,
        app_id=app_id,
        status=status,
        batch_no=batch_no,
    )
    return response_base.success(data=page_data)


@router.post(
    '/batches',
    summary='创建兑换批次',
    dependencies=[
        Depends(RequestPermission('access:redeem:create')),
        DependsRBAC,
    ],
)
async def create_redeem_batch(
    db: CurrentSessionTransaction,
    obj: CreateRedeemBatchParam,
) -> ResponseSchemaModel[GetRedeemBatchDetail]:
    """创建兑换批次"""
    data = await access_redeem_service.create_batch(db=db, obj=obj)
    return response_base.success(data=data)


@router.put(
    '/batches/{pk}',
    summary='更新兑换批次',
    dependencies=[
        Depends(RequestPermission('access:redeem:update')),
        DependsRBAC,
    ],
)
async def update_redeem_batch(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='批次 ID')],
    obj: UpdateRedeemBatchParam,
) -> ResponseModel:
    """更新兑换批次"""
    count = await access_redeem_service.update_batch(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.get(
    '/agiso-rules',
    summary='获取阿奇索批次匹配规则',
    dependencies=[DependsJwtAuth],
)
async def get_agiso_batch_rules(
    db: CurrentSession,
) -> ResponseSchemaModel[list[AgisoBatchRuleParam]]:
    """获取阿奇索批次匹配规则"""
    data = await access_redeem_service.get_agiso_rules(db=db)
    return response_base.success(data=data)


@router.put(
    '/agiso-rules',
    summary='设置阿奇索批次匹配规则',
    dependencies=[
        Depends(RequestPermission('access:redeem:update')),
        DependsRBAC,
    ],
)
async def set_agiso_batch_rules(
    db: CurrentSessionTransaction,
    obj: SetAgisoBatchRulesParam,
) -> ResponseSchemaModel[list[AgisoBatchRuleParam]]:
    """设置阿奇索批次匹配规则"""
    data = await access_redeem_service.set_agiso_rules(db=db, obj=obj)
    return response_base.success(data=data)
