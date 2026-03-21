#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.auth.model.social_account import UserSocialAccount


class CRUDSocialAccount(CRUDPlus[UserSocialAccount]):
    """社交账号绑定数据库操作类"""

    async def get_by_openid(
        self, db: AsyncSession, platform: str, openid: str
    ) -> UserSocialAccount | None:
        """
        按平台和 openid 查找

        :param db: 数据库会话
        :param platform: 平台标识
        :param openid: 平台 OpenID
        :return:
        """
        return await self.select_model_by_column(
            db, platform__eq=platform, openid__eq=openid, status__eq=1
        )

    async def get_by_unionid(self, db: AsyncSession, unionid: str) -> SocialAccount | None:
        """
        按 unionid 查找（跨端匹配优先）

        :param db: 数据库会话
        :param unionid: 微信 UnionID
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.unionid == unionid, self.model.status == 1)
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_user_id(self, db: AsyncSession, user_id: int) -> Sequence[UserSocialAccount]:
        """
        获取用户所有社交绑定

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.user_id == user_id, self.model.status == 1)
            .order_by(self.model.created_time.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def update_session_key(
        self, db: AsyncSession, account_id: int, session_key: str
    ) -> None:
        """
        更新小程序 session_key

        :param db: 数据库会话
        :param account_id: 社交账号 ID
        :param session_key: 新的 session_key
        :return:
        """
        stmt = (
            update(self.model)
            .where(self.model.id == account_id)
            .values(session_key=session_key)
        )
        await db.execute(stmt)

    async def get_user_openid(
        self, db: AsyncSession, user_id: int, platform: str
    ) -> str | None:
        """
        获取用户在指定平台的 openid（供支付等场景使用）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param platform: 平台标识
        :return:
        """
        stmt = (
            select(self.model.openid)
            .where(
                self.model.user_id == user_id,
                self.model.platform == platform,
                self.model.status == 1,
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


social_account_dao: CRUDSocialAccount = CRUDSocialAccount(UserSocialAccount)
