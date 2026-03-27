#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_user import user_account_dao
from backend.app.question_bank.model.user import UserAccount


class UserAccountService:
    """题库用户账户服务类"""

    @staticmethod
    async def ensure_by_sys_user_id(
        *,
        db: AsyncSession,
        sys_user_id: int,
        register_channel: str | None = None,
    ) -> UserAccount:
        """
        确保题库扩展账户存在

        :param db: 数据库会话
        :param sys_user_id: 系统用户 ID
        :param register_channel: 注册渠道
        :return:
        """
        account = await user_account_dao.get_by_sys_user_id(db, sys_user_id)
        if account:
            if register_channel and not account.register_channel:
                account.register_channel = register_channel
                await db.flush()
            return account

        account = UserAccount(user_id=sys_user_id, register_channel=register_channel)
        db.add(account)
        await db.flush()
        return account


user_account_service = UserAccountService()
