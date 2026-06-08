#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.growth.crud.crud_growth_event import growth_event_dao
from backend.app.growth.schema.account import GetGrowthEventDetail, GetGrowthProgress
from backend.app.growth.service.experience_service import experience_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get(
    '/progress',
    summary='我的成长进度',
    dependencies=[DependsJwtAuth],
)
async def get_my_progress(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[GetGrowthProgress | None]:
    """我的成长进度"""
    user_id = int(request.user.id)
    data = await experience_service.get_user_progress(db, user_id=user_id)
    return response_base.success(data=data)


@router.get(
    '/events',
    summary='我的成长流水',
    dependencies=[DependsJwtAuth],
)
async def get_my_events(
    request: Request,
    db: CurrentSession,
    limit: Annotated[int, Query(ge=1, le=100, description='数量上限')] = 50,
) -> ResponseSchemaModel[list[GetGrowthEventDetail]]:
    """我的成长流水"""
    user_id = int(request.user.id)
    data = await growth_event_dao.list_by_user(db, user_id=user_id, limit=limit)
    return response_base.success(data=data)
