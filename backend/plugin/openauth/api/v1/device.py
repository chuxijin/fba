from fastapi import APIRouter, Request

from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.openauth.dependencies import OpenAuthBearerToken
from backend.plugin.openauth.schema.device import (
    CreateOpenAuthDeviceRevokeParam,
    GetOpenAuthDeviceRevokePreview,
    GetOpenAuthDeviceRevokeTicket,
)
from backend.plugin.openauth.service.device_service import openauth_device_service

router = APIRouter()


@router.post('/unauthorize', summary='生成当前设备解绑确认链接凭证')
async def create_openauth_device_revoke_ticket(
    db: CurrentSessionTransaction,
    token: OpenAuthBearerToken,
) -> ResponseSchemaModel[GetOpenAuthDeviceRevokeTicket]:
    return response_base.success(data=await openauth_device_service.create_ticket(db, token=token))


@router.post('/device-revoke/preview', summary='设备解绑确认页预览', dependencies=[DependsJwtAuth])
async def get_openauth_device_revoke_preview(
    request: Request,
    db: CurrentSession,
    obj: CreateOpenAuthDeviceRevokeParam,
) -> ResponseSchemaModel[GetOpenAuthDeviceRevokePreview]:
    data = await openauth_device_service.preview(db, user_id=int(request.user.id), ticket=obj.ticket)
    return response_base.success(data=data)


@router.post('/device-revoke', summary='确认解绑当前设备', dependencies=[DependsJwtAuth])
async def revoke_openauth_device(request: Request, obj: CreateOpenAuthDeviceRevokeParam) -> ResponseModel:
    await openauth_device_service.revoke(user_id=int(request.user.id), ticket=obj.ticket)
    return response_base.success()
