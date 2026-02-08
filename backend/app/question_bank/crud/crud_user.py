#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.admin.model import User
from backend.app.question_bank.model import UserAccount


class CRUDUserAccount(CRUDPlus[UserAccount]):
    """用户账户数据库操作类"""

    async def get(self, db: AsyncSession, user_id: int) -> UserAccount | None:
        """
        获取用户详情（含关联的 sys_user）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(UserAccount).where(UserAccount.id == user_id).options(selectinload(UserAccount.user))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_openid(self, db: AsyncSession, openid: str) -> UserAccount | None:
        """
        通过 OpenID 获取用户

        :param db: 数据库会话
        :param openid: 微信 OpenID
        :return:
        """
        stmt = select(UserAccount).where(UserAccount.open_id == openid).options(selectinload(UserAccount.user))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_unionid(self, db: AsyncSession, unionid: str) -> UserAccount | None:
        """
        通过 UnionID 获取用户

        :param db: 数据库会话
        :param unionid: 微信 UnionID
        :return:
        """
        stmt = select(UserAccount).where(UserAccount.union_id == unionid).options(selectinload(UserAccount.user))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_wx_user(
        self,
        db: AsyncSession,
        openid: str,
        unionid: str | None = None,
        session_key: str | None = None,
        nickname: str = '微信用户',
        avatar: str | None = None,
        platform: str = 'miniapp',
        username: str | None = None,
    ) -> UserAccount:
        """
        创建微信用户（同时创建 sys_user 和 study_user_account）

        :param db: 数据库会话
        :param openid: 微信 OpenID
        :param unionid: 微信 UnionID
        :param session_key: 微信 SessionKey
        :param nickname: 昵称
        :param avatar: 头像
        :param platform: 平台
        :param username: 用户名（可选，不传则自动生成）
        :return:
        """
        # 如果没有传入 username，则自动生成
        if not username:
            username = f'wx_{uuid.uuid4().hex[:12]}'

        # 1. 先创建 sys_user 记录
        sys_user = User(
            username=username,
            nickname=nickname,
            avatar=avatar,
            status=1,
        )
        db.add(sys_user)
        await db.flush()

        # 2. 再创建 study_user_account 关联记录
        account = UserAccount(
            user_id=sys_user.id,
            open_id=openid,
            union_id=unionid,
            session_key=session_key,
            register_channel=platform,
        )
        db.add(account)
        await db.flush()

        # 设置关联关系便于返回后使用
        account.user = sys_user
        return account

    async def update_session_key(self, db: AsyncSession, user_id: int, session_key: str) -> int:
        """
        更新 session_key

        :param db: 数据库会话
        :param user_id: 用户 ID（study_user_account.id）
        :param session_key: 新的 session_key
        :return:
        """
        return await self.update_model(db, user_id, {'session_key': session_key})

    async def update_phone(self, db: AsyncSession, user_id: int, phone: str) -> int:
        """
        更新手机号（更新 sys_user）

        :param db: 数据库会话
        :param user_id: 用户 ID（study_user_account.id）
        :param phone: 手机号
        :return:
        """
        account = await self.get(db, user_id)
        if not account:
            return 0
        stmt = select(User).where(User.id == account.user_id)
        result = await db.execute(stmt)
        sys_user = result.scalar_one_or_none()
        if sys_user:
            sys_user.phone = phone
            await db.flush()
            return 1
        return 0

    async def update_nickname(self, db: AsyncSession, user_id: int, nickname: str) -> int:
        """
        更新昵称（更新 sys_user）

        :param db: 数据库会话
        :param user_id: 用户 ID（study_user_account.id）
        :param nickname: 昵称
        :return:
        """
        account = await self.get(db, user_id)
        if not account:
            return 0
        stmt = select(User).where(User.id == account.user_id)
        result = await db.execute(stmt)
        sys_user = result.scalar_one_or_none()
        if sys_user:
            sys_user.nickname = nickname
            await db.flush()
            return 1
        return 0

    async def update_avatar(self, db: AsyncSession, user_id: int, avatar: str) -> int:
        """
        更新头像（更新 sys_user）

        :param db: 数据库会话
        :param user_id: 用户 ID（study_user_account.id）
        :param avatar: 头像 URL
        :return:
        """
        account = await self.get(db, user_id)
        if not account:
            return 0
        stmt = select(User).where(User.id == account.user_id)
        result = await db.execute(stmt)
        sys_user = result.scalar_one_or_none()
        if sys_user:
            sys_user.avatar = avatar
            await db.flush()
            return 1
        return 0


user_account_dao: CRUDUserAccount = CRUDUserAccount(UserAccount)
