from fastapi import APIRouter, Request, Depends
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.db import get_db

from backend.app.jia.schema.user_setting import GetUserSettingDetail, UpdateUserSettingParam
from backend.app.jia.service.user_setting_service import user_setting_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth

router = APIRouter()

@router.get('/settings', summary='获取当前用户个人设置', response_model=ResponseSchemaModel[GetUserSettingDetail], dependencies=[DependsJwtAuth])
async def get_my_settings(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseSchemaModel[GetUserSettingDetail]:
    settings = await user_setting_service.get_my_settings(db=db, user_id=request.user.id)
    return response_base.success(data=settings)

@router.put('/settings', summary='更新当前用户个人设置', response_model=ResponseSchemaModel[GetUserSettingDetail], dependencies=[DependsJwtAuth])
async def update_my_settings(
    request: Request,
    obj: UpdateUserSettingParam,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseSchemaModel[GetUserSettingDetail]:
    settings = await user_setting_service.update_my_settings(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=settings)
