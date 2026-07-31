from fastapi import APIRouter, Request

from backend.app.question_bank_v2.schema.preference import GetPracticePreferenceDetail, UpdatePracticePreferenceParam
from backend.app.question_bank_v2.service.practice_data_reset_service import (
    PracticeDataResetResult,
    practice_data_reset_service,
)
from backend.app.question_bank_v2.service.preference_service import preference_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '',
    summary='获取用户练习偏好',
    name='qbank_v2_get_practice_preference',
    dependencies=[DependsJwtAuth],
)
async def get_practice_preference(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[GetPracticePreferenceDetail]:
    """未初始化时返回稳定默认偏好"""
    data = await preference_service.get(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.put(
    '',
    summary='更新用户练习偏好',
    name='qbank_v2_update_practice_preference',
    dependencies=[DependsJwtAuth],
)
async def update_practice_preference(
    request: Request,
    db: CurrentSessionTransaction,
    obj: UpdatePracticePreferenceParam,
) -> ResponseSchemaModel[GetPracticePreferenceDetail]:
    """按需创建或局部更新用户练习偏好"""
    data = await preference_service.update(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.delete(
    '/practice-data',
    summary='重置练习数据',
    name='qbank_v2_reset_practice_data',
    dependencies=[DependsJwtAuth],
)
async def reset_practice_data(
    request: Request,
    db: CurrentSessionTransaction,
) -> ResponseSchemaModel[PracticeDataResetResult]:
    """清除当前用户所有练习、作答、错题和统计投影数据"""
    data = await practice_data_reset_service.reset_user_practice_data(
        db=db,
        user_id=request.user.id,
    )
    return response_base.success(data=data)
