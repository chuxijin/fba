#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.growth.schema.account import GetGrowthAccountDetail
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
    family_code: Annotated[str | None, Query(description='族群过滤')] = None,
) -> ResponseSchemaModel[list[GetGrowthAccountDetail]]:
    """我的成长进度"""
    user_id = int(request.user.id)
    data = await experience_service.get_user_progress(
        db, user_id=user_id, family_code=family_code
    )
    return response_base.success(data=data)
