#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.question_bank.crud.crud_user import user_account_dao
from backend.app.question_bank.schema.customer import GetCustomerInfo, UpdateProfileParam
from backend.app.question_bank.security import DependsCustomerAuth
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/me', summary='获取当前用户信息')
async def get_current_user_info(
    db: CurrentSession, current_user: AuthUser = DependsCustomerAuth
) -> ResponseSchemaModel[GetCustomerInfo]:
    """
    获取当前用户信息（含会员权益）

    :return: 用户信息 + 会员权益列表
    """
    try:
        # 获取用户基础信息
        user = await user_account_dao.get(db, current_user.user_id)
        if not user:
            return response_base.fail(res=CustomResponse(code=404, msg='用户不存在'))

        data = GetCustomerInfo(
            id=user.id,
            username=user.user.username,
            nickname=user.user.nickname or '微信用户',
            avatar=user.user.avatar,
            memberships=[],  # TODO: 会员权益后续补充
        )

        return response_base.success(data=data)
    except Exception as e:
        print(f'[Customer API] 获取用户信息失败: {e}')
        import traceback
        traceback.print_exc()
        return response_base.fail(res=CustomResponse(code=500, msg=f'获取用户信息失败: {str(e)}'))


@router.put('/profile', summary='更新用户资料')
async def update_profile(
    db: CurrentSessionTransaction, obj: UpdateProfileParam, current_user: AuthUser = DependsCustomerAuth
) -> ResponseSchemaModel:
    """更新用户资料（昵称、头像等）"""
    try:
        user = await user_account_dao.get(db, current_user.user_id)
        if not user:
            return response_base.fail(res=CustomResponse(code=404, msg='用户不存在'))

        # 更新昵称
        if obj.nickname is not None:
            await user_account_dao.update_nickname(db, user.id, obj.nickname)

        # 更新头像
        if obj.avatar is not None:
            await user_account_dao.update_avatar(db, user.id, obj.avatar)

        return response_base.success(data={'msg': '资料更新成功'})
    except Exception as e:
        print(f'[Customer API] 更新用户资料失败: {e}')
        import traceback
        traceback.print_exc()
        return response_base.fail(res=CustomResponse(code=500, msg=f'更新资料失败: {str(e)}'))
