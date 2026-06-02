#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request

from backend.app.question_bank.schema.user_settings import (
    GetStudyPreferenceResponse,
    InitCategoryPreferenceParam,
    PracticeDataResetResult,
    UpdateStudyPreferenceParam,
)
from backend.app.question_bank.service.practice_data_reset_service import practice_data_reset_service
from backend.app.question_bank.service.user_settings_service import user_settings_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/study-preference', summary='获取学习偏好设置', name='qbank_get_study_preference', dependencies=[DependsJwtAuth])
async def get_study_preference(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[GetStudyPreferenceResponse]:
    """获取学习偏好设置"""
    data = await user_settings_service.get_study_preference(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.put('/study-preference', summary='更新学习偏好设置', name='qbank_update_study_preference', dependencies=[DependsJwtAuth])
async def update_study_preference(
    request: Request,
    db: CurrentSessionTransaction,
    param: UpdateStudyPreferenceParam,
) -> ResponseModel:
    """更新学习偏好设置"""
    await user_settings_service.update_study_preference(
        db=db,
        user_id=request.user.id,
        current_cat_id=param.current_cat_id,
        current_kp_cat_id=param.current_kp_cat_id,
        practice_mode=param.practice_mode,
        category_custom_tabs=param.category_custom_tabs,
        mastery_threshold=param.mastery_threshold,
        theme_mode=param.theme_mode,
    )
    return response_base.success()


@router.post(
    '/study-preference/init-category',
    summary='新用户初始化分类偏好',
    name='qbank_init_category_preference',
    dependencies=[DependsJwtAuth],
)
async def init_category_preference(
    request: Request,
    db: CurrentSessionTransaction,
    param: InitCategoryPreferenceParam,
) -> ResponseModel:
    """新用户选择分类后初始化默认偏好"""
    category_custom_tabs = await user_settings_service.initialize_category_preference(
        db=db,
        user_id=request.user.id,
        cat_id=param.cat_id,
        kp_cat_id=param.kp_cat_id,
    )
    return response_base.success(data={'category_custom_tabs': category_custom_tabs})


@router.delete('/practice-data', summary='重置做题数据', name='qbank_reset_practice_data', dependencies=[DependsJwtAuth])
async def reset_practice_data(
    request: Request,
    db: CurrentSessionTransaction,
) -> ResponseSchemaModel[PracticeDataResetResult]:
    """重置做题数据"""
    data = await practice_data_reset_service.reset_user_practice_data(db=db, user_id=request.user.id)
    return response_base.success(data=data)
