#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.bili.crud import bili_account_dao
from backend.app.bili.model import BiliAccount
from backend.app.bili.schema.account import CreateBiliAccountParam, UpdateBiliAccountParam
from backend.common.exception import errors


class BiliAccountService:
    """B 站账号服务类"""

    @staticmethod
    async def get(db: AsyncSession, pk: int) -> BiliAccount:
        """
        获取账号详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        account = await bili_account_dao.get(db, pk)
        if not account:
            raise errors.NotFoundError(msg='账号不存在')
        return account

    @staticmethod
    async def get_by_mid(db: AsyncSession, mid: str) -> BiliAccount:
        """
        通过 MID 获取账号

        :param db: 数据库会话
        :param mid: B 站用户 MID
        :return:
        """
        account = await bili_account_dao.get_by_mid(db, mid)
        if not account:
            raise errors.NotFoundError(msg='账号不存在')
        return account

    @staticmethod
    async def create(db: AsyncSession, obj: CreateBiliAccountParam) -> None:
        """
        创建账号

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        if obj.mid:
            account = await bili_account_dao.get_by_mid(db, obj.mid)
            if account:
                raise errors.ForbiddenError(msg='MID 已存在')
        await bili_account_dao.create(db, obj)

    @staticmethod
    async def update(db: AsyncSession, pk: int, obj: UpdateBiliAccountParam) -> int:
        """
        更新账号

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        account = await bili_account_dao.get(db, pk)
        if not account:
            raise errors.NotFoundError(msg='账号不存在')
        if obj.mid and obj.mid != account.mid:
            exist_account = await bili_account_dao.get_by_mid(db, obj.mid)
            if exist_account:
                raise errors.ForbiddenError(msg='MID 已存在')
        count = await bili_account_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(db: AsyncSession, pk: int) -> int:
        """
        删除账号

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        account = await bili_account_dao.get(db, pk)
        if not account:
            raise errors.NotFoundError(msg='账号不存在')
        count = await bili_account_dao.delete(db, pk)
        return count


bili_account_service = BiliAccountService()
