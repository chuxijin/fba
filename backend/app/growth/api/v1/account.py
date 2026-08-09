#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from backend.app.growth.crud.crud_growth_event import growth_event_dao
from backend.app.growth.model.account import GrowthAccount
from backend.app.growth.schema.account import (
    GetGrowthAccountDetail,
    GetGrowthEventDetail,
    ManualExperienceParam,
)
from backend.app.growth.service.experience_service import experience_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '',
    summary='分页查询经验账户',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_account_list(
    db: CurrentSession,
    user_id: Annotated[int | None, Query(description='用户 ID')] = None,
) -> ResponseSchemaModel[PageData[GetGrowthAccountDetail]]:
    """分页查询经验账户"""
    stmt = select(GrowthAccount)
    if user_id is not None:
        stmt = stmt.where(GrowthAccount.user_id == user_id)
    stmt = stmt.order_by(GrowthAccount.user_id.asc())
    page_data = await paging_data(db, stmt)
    return response_base.success(data=page_data)


@router.post('/grant', summary='管理端发放经验')
async def grant_experience(db: CurrentSessionTransaction, obj: ManualExperienceParam) -> ResponseModel:
    """管理端向用户发放经验值"""
    await experience_service.add_experience(
        db,
        user_id=obj.user_id,
        exp_delta=obj.exp_delta,
        source='admin',
        source_key=obj.source_key,
        reason=obj.reason,
    )
    return response_base.success()


@router.post('/consume', summary='管理端扣减经验')
async def consume_experience(db: CurrentSessionTransaction, obj: ManualExperienceParam) -> ResponseModel:
    """管理端扣减用户可用经验值"""
    await experience_service.consume_experience(
        db,
        user_id=obj.user_id,
        exp_delta=obj.exp_delta,
        source='admin',
        source_key=obj.source_key,
        reason=obj.reason,
    )
    return response_base.success()


@router.get(
    '/records',
    summary='分页查询经验流水',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_experience_records(
    db: CurrentSession,
    user_id: Annotated[int | None, Query(gt=0, description='用户 ID')] = None,
    operation: Annotated[str | None, Query(description='操作类型')] = None,
    source: Annotated[str | None, Query(description='来源')] = None,
) -> ResponseSchemaModel[PageData[GetGrowthEventDetail]]:
    """分页查询经验流水"""
    stmt = await growth_event_dao.get_select(user_id=user_id, operation=operation, source=source)
    page_data = await paging_data(db, stmt)
    return response_base.success(data=page_data)
