#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import UserAccount


class CRUDUserAccount(CRUDPlus[UserAccount]):
    """用户账户数据库操作类"""

    async def get(self, db: AsyncSession, user_id: int) -> UserAccount | None:
        """
        获取用户详情

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_model_by_column(db, id=user_id)

    async def get_by_openid(self, db: AsyncSession, openid: str) -> UserAccount | None:
        """
        通过 OpenID 获取用户

        :param db: 数据库会话
        :param openid: 微信 OpenID
        :return:
        """
        return await self.select_model_by_column(db, open_id=openid)

    async def get_by_unionid(self, db: AsyncSession, unionid: str) -> UserAccount | None:
        """
        通过 UnionID 获取用户

        :param db: 数据库会话
        :param unionid: 微信 UnionID
        :return:
        """
        return await self.select_model_by_column(db, union_id=unionid)

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
        创建微信用户

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
        import uuid

        # 如果没有传入 username，则自动生成
        if not username:
            username = f'wx_{uuid.uuid4().hex[:12]}'

        user_data = {
            'open_id': openid,
            'union_id': unionid,
            'session_key': session_key,
            'username': username,
            'nickname': nickname,
            'avatar': avatar,
            'register_channel': platform,
            'status': 1,
        }

        user = UserAccount(**user_data)
        db.add(user)
        await db.flush()
        return user

    async def update_session_key(self, db: AsyncSession, user_id: int, session_key: str) -> int:
        """
        更新 session_key

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_key: 新的 session_key
        :return:
        """
        return await self.update_model(db, user_id, {'session_key': session_key})

    async def update_phone(self, db: AsyncSession, user_id: int, phone: str) -> int:
        """
        更新手机号

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param phone: 手机号
        :return:
        """
        return await self.update_model(db, user_id, {'phone': phone})

    async def update_nickname(self, db: AsyncSession, user_id: int, nickname: str) -> int:
        """
        更新昵称

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param nickname: 昵称
        :return:
        """
        return await self.update_model(db, user_id, {'nickname': nickname})

    async def update_avatar(self, db: AsyncSession, user_id: int, avatar: str) -> int:
        """
        更新头像

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param avatar: 头像 URL
        :return:
        """
        return await self.update_model(db, user_id, {'avatar': avatar})


user_account_dao: CRUDUserAccount = CRUDUserAccount(UserAccount)
