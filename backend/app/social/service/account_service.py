#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy import Select

from backend.app.social.crud.crud_account import social_account_dao
from backend.app.social.model.account import SocialAccount
from backend.app.social.schema.account import (
    CreateSocialAccountParam,
    UpdateSocialAccountParam,
)
from backend.common.exception import errors
from backend.database.db import async_db_session


class SocialAccountService:
    """账号服务类"""

    @staticmethod
    async def get(*, pk: int) -> SocialAccount:
        """
        获取账号详情

        :param pk: 账号 ID
        :return:
        """
        async with async_db_session() as db:
            account = await social_account_dao.get(db, pk)
            if not account:
                raise errors.NotFoundError(msg='账号不存在')
            return account

    @staticmethod
    async def get_list(*, platform: str | None, name: str | None, domain: str | None = None) -> Select:
        """获取账号列表查询语句"""
        return await social_account_dao.get_list(platform=platform, name=name, domain=domain)

    @staticmethod
    async def create(*, obj: CreateSocialAccountParam, current_user_id: int) -> SocialAccount:
        """创建账号"""
        async with async_db_session() as db:
            existed = await social_account_dao.get_by_platform_name(db, platform=obj.platform, name=obj.name)
            if existed:
                raise errors.ConflictError(msg='账号已存在')
            account = await social_account_dao.create(db, obj, current_user_id)
            return account

    @staticmethod
    async def update(*, pk: int, obj: UpdateSocialAccountParam, current_user_id: int) -> int:
        """更新账号"""
        async with async_db_session() as db:
            count = await social_account_dao.update(db, pk, obj, current_user_id)
            if count == 0:
                raise errors.NotFoundError(msg='账号不存在')
            return count

    @staticmethod
    async def delete(*, pks: list[int]) -> int:
        """删除账号"""
        async with async_db_session() as db:
            return await social_account_dao.delete(db, pks)
