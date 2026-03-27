#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request

from backend.app.admin.schema.user import GetCurrentUserInfoWithRelationDetail
from backend.app.question_bank.service.user_account_service import user_account_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSessionTransaction

router = APIRouter()


@router.get('/me', summary='获取题库当前用户信息', dependencies=[DependsJwtAuth])
async def get_current_user_info(
    request: Request,
    db: CurrentSessionTransaction,
) -> ResponseSchemaModel[GetCurrentUserInfoWithRelationDetail]:
    """
    获取题库当前用户信息

    首次进入题库产品时，会自动补齐题库扩展账户。
    """
    await user_account_service.ensure_by_sys_user_id(
        db=db,
        sys_user_id=request.user.id,
        register_channel='account',
    )

    data = request.user.model_dump()

    from backend.app.admin.crud.crud_user_role_expiry import user_role_expiry_dao

    expiry_records = await user_role_expiry_dao.get_by_user(db, request.user.id)
    if expiry_records:
        raw_roles = request.user.roles or []
        role_id_name_map = {role.id: role.name for role in raw_roles}
        data['role_expiries'] = [
            {
                'role_id': item.role_id,
                'role_name': role_id_name_map.get(item.role_id, ''),
                'valid_from': item.valid_from,
                'valid_to': item.valid_to,
                'status': item.status,
            }
            for item in expiry_records
        ]

    return response_base.success(data=data)
