#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Request

from backend.app.gongkao.schema.gangwei_match import CanApplyResult
from backend.app.gongkao.service.gangwei_match_service import gangwei_match_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get(
    '/{gangwei_id}/can-apply',
    summary='检查能否报考岗位',
    dependencies=[DependsJwtAuth],
)
async def check_can_apply(
    request: Request,
    db: CurrentSession,
    gangwei_id: Annotated[int, Path(description='岗位 ID')],
) -> ResponseSchemaModel[CanApplyResult]:
    """
    检查当前用户能否报考指定岗位

    返回:
    - can_apply: 是否可以报考
    - reasons: 不能报考的原因列表
    - checks: 各条件的详细检查结果
    """
    result = await gangwei_match_service.check_can_apply(
        db=db,
        gangwei_id=gangwei_id,
        user_id=request.user.id,
    )
    return response_base.success(data=result)
