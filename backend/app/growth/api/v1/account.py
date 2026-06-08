#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from backend.app.growth.model.account import GrowthAccount
from backend.app.growth.schema.account import GetGrowthAccountDetail
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

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
