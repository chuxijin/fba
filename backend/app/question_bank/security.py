#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import Depends, Request
from sqlalchemy.exc import IntegrityError

from backend.app.auth.security import get_current_user as get_auth_user
from backend.app.question_bank.crud.crud_user import user_account_dao
from backend.app.question_bank.model import UserAccount
from backend.common.exception import errors
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import async_db_session


async def ensure_user_account(sys_user_id: int, username: str | None) -> UserAccount:
    """
    确保存在对应的 C 端账户

    :param sys_user_id: 系统用户 ID
    :param username: 用户名
    :return:
    """
    async with async_db_session.begin() as db:
        account = await user_account_dao.get_by_sys_user_id(db, sys_user_id)
        if account:
            return account

        account = UserAccount(user_id=sys_user_id, register_channel='auto')
        db.add(account)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            account = await user_account_dao.get_by_sys_user_id(db, sys_user_id)
            if account:
                return account
            raise errors.ServerError(msg='创建用户账户失败')

        return account


async def get_current_user(request: Request) -> AuthUser:
    """
    获取当前用户（question_bank 专用，返回 study_user_account.id）

    在 auth 模块返回 sys_user.id 的基础上，解析为 study_user_account.id，
    保持 question_bank 内所有 current_user.user_id 的语义不变。

    :param request: 请求对象
    :return:
    """
    auth_user = await get_auth_user(request)

    # 将 sys_user.id 解析为 study_user_account.id
    account = await ensure_user_account(auth_user.user_id, auth_user.username)
    return AuthUser(
        user_id=account.id,
        user_type=auth_user.user_type,
        username=auth_user.username,
    )


# 依赖注入快捷方式（返回 study_user_account.id 级别的身份）
DependsCurrentUser = Depends(get_current_user)
