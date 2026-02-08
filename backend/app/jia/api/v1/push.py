#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request

from backend.app.jia.crud import device_dao
from backend.app.jia.schema import (
    DeviceRegisterParam,
    GetDeviceDetail,
    PushToUserParam,
    PushToDeviceParam,
    PushToAllParam,
    PushResult,
)
from backend.app.jia.service import push_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.post('/device/register', summary='注册设备', dependencies=[DependsJwtAuth])
async def register_device(
    request: Request,
    db: CurrentSession,
    obj: DeviceRegisterParam,
) -> ResponseSchemaModel[GetDeviceDetail]:
    """
    注册设备以接收推送通知

    - 如果设备已存在，则更新信息
    - 需要登录后调用
    """
    user_id = request.user.id
    device = await device_dao.register(db, user_id, obj)
    await db.commit()
    return response_base.success(data=device)


@router.delete('/device/unregister', summary='注销设备', dependencies=[DependsJwtAuth])
async def unregister_device(
    request: Request,
    db: CurrentSession,
    fcm_token: str,
) -> ResponseModel:
    """注销设备，停止接收推送通知"""
    await device_dao.deactivate(db, fcm_token)
    await db.commit()
    return response_base.success()


@router.get('/device/list', summary='获取我的设备列表', dependencies=[DependsJwtAuth])
async def get_my_devices(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetDeviceDetail]]:
    """获取当前用户的所有注册设备"""
    user_id = request.user.id
    devices = await device_dao.get_by_user_id(db, user_id)
    return response_base.success(data=devices)


@router.post('/push/to-device', summary='推送到指定设备', dependencies=[DependsJwtAuth])
async def push_to_device(
    obj: PushToDeviceParam,
) -> ResponseSchemaModel[PushResult]:
    """推送消息到指定设备（通过 FCM Token）"""
    result = await push_service.send_to_token(
        token=obj.fcm_token,
        title=obj.title,
        body=obj.body,
        data=obj.data,
    )
    return response_base.success(data=result)


@router.post('/push/to-user', summary='推送到指定用户', dependencies=[DependsJwtAuth])
async def push_to_user(
    db: CurrentSession,
    obj: PushToUserParam,
) -> ResponseSchemaModel[list[PushResult]]:
    """推送消息到指定用户的所有设备"""
    results = await push_service.send_to_user(
        db=db,
        user_id=obj.user_id,
        title=obj.title,
        body=obj.body,
        data=obj.data,
    )
    await db.commit()
    return response_base.success(data=results)


@router.post('/push/to-all', summary='推送到所有用户', dependencies=[DependsJwtAuth])
async def push_to_all(
    db: CurrentSession,
    obj: PushToAllParam,
) -> ResponseSchemaModel[list[PushResult]]:
    """推送消息到所有活跃设备"""
    results = await push_service.send_to_all(
        db=db,
        title=obj.title,
        body=obj.body,
        data=obj.data,
    )
    await db.commit()
    return response_base.success(data=results)


@router.post('/push/test', summary='测试推送', dependencies=[DependsJwtAuth])
async def test_push(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[PushResult]]:
    """发送测试推送到当前用户的所有设备"""
    user_id = request.user.id
    results = await push_service.send_to_user(
        db=db,
        user_id=user_id,
        title='测试推送',
        body='这是一条测试消息，如果你收到说明推送配置成功！',
        data={'type': 'test'},
    )
    await db.commit()
    return response_base.success(data=results)
