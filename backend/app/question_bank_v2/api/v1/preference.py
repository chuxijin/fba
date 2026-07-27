from fastapi import APIRouter, Request

from backend.app.question_bank_v2.schema.preference import GetPracticePreferenceDetail, UpdatePracticePreferenceParam
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
