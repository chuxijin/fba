#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Body

from backend.app.actcode.schema.actcode import RedeemCodeResult
from backend.app.question_bank.security import DependsCurrentUser
from backend.app.question_bank.service.activation_service import activation_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSession

router = APIRouter(prefix='/activation', tags=['激活码'])


@router.post('/query', summary='查询激活码信息')
async def query_activation_code(
    db: CurrentSession,
    code: Annotated[str, Body(..., description='激活码', embed=True)],
) -> ResponseSchemaModel[RedeemCodeResult]:
    """查询激活码信息（不实际激活）"""
    result = await activation_service.query_code_info(db=db, code=code)
    return response_base.success(data=result)


@router.post('/redeem', summary='兑换激活码')
async def redeem_activation_code(
    db: CurrentSession,
    code: Annotated[str, Body(..., description='激活码', embed=True)],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[RedeemCodeResult]:
    """兑换激活码并自动创建会员权益"""
    result = await activation_service.redeem_code_for_qbank(
        db=db,
        user_id=current_user.user_id,
        code=code,
    )
    return response_base.success(data=result)

