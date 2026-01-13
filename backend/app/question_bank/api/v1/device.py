#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request

from backend.app.question_bank.crud.crud_device import user_device_dao
from backend.app.question_bank.schema.device import UpdateDeviceParam
from backend.app.question_bank.security import DependsCustomerAuth
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSessionTransaction

router = APIRouter()


@router.post('/update', summary='更新设备信息', name='qbank_update_device')
async def update_device_info(
    request: Request,
    db: CurrentSessionTransaction,
    params: UpdateDeviceParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[dict]:
    """
    更新设备信息

    用于应用启动或从后台恢复时同步设备状态
    """
    # 获取客户端 IP
    client_ip = request.client.host if request.client else None

    # 更新设备信息
    await user_device_dao.create_or_update_device(
        db=db,
        user_id=current_user.user_id,
        device_id=params.device_id,
        platform='miniapp',
        device_model=params.device_model,
        os_version=params.os_version,
        app_version=params.app_version,
        push_token=params.push_token,
        last_ip=client_ip,
    )

    return response_base.success(data={'message': '设备信息已更新'})
