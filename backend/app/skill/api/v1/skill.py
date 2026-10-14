#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.skill.service import ensure_skill_access, get_skill_entitlement_status
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import get_current_user
from backend.database.db import CurrentSessionTransaction
from backend.plugin.openauth.dependencies import RequireOpenAuth
from backend.plugin.openauth.schema.authorization import GetOpenAuthCheckResult

router = APIRouter()


@router.get('/status', summary='skill 使用资格与账号状态')
async def get_skill_status(
    db: CurrentSessionTransaction,
    identity: Annotated[GetOpenAuthCheckResult, Depends(RequireOpenAuth('skill:use'))],
) -> ResponseSchemaModel:
    """CLI 第一步调用：账号资料 + 会员资格（资格不足不拦截，deny 信息原样下发供引导）"""
    can_use, deny_message = await get_skill_entitlement_status(db, user_id=identity.user_id)
    user = await get_current_user(db, identity.user_id)
    return response_base.success(
        data={
            'user_id': user.id,
            'nickname': user.nickname or '用户',
            'avatar': user.avatar,
            'can_use': can_use,
            'deny_message': deny_message,
        }
    )
