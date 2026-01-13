#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户设置接口
"""
from fastapi import APIRouter

from backend.app.question_bank.schema.user_settings import (
    GetStudyPreferenceResponse,
    UpdateStudyPreferenceParam,
)
from backend.app.question_bank.security import DependsCustomerAuth
from backend.app.question_bank.service.user_settings_service import user_settings_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/study-preference', summary='获取学习偏好设置', name='qbank_get_study_preference')
async def get_study_preference(
    db: CurrentSession,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetStudyPreferenceResponse]:
    """获取学习偏好设置"""
    data = await user_settings_service.get_study_preference(db=db, user_id=current_user.user_id)
    return response_base.success(data=data)


@router.put('/study-preference', summary='更新学习偏好设置', name='qbank_update_study_preference')
async def update_study_preference(
    db: CurrentSessionTransaction,
    param: UpdateStudyPreferenceParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """更新学习偏好设置"""
    await user_settings_service.update_study_preference(
        db=db,
        user_id=current_user.user_id,
        practice_mode=param.practice_mode,
        custom_tabs=param.custom_tabs,
    )

    return response_base.success(data='success')
