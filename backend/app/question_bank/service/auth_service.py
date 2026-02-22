#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_user import user_account_dao
from backend.app.question_bank.model import UserAccount
from backend.app.question_bank.utils.wx_decrypt import WXBizDataCrypt
from backend.common.exception import errors
from backend.common.security.unified_token import create_unified_token
from backend.core.conf import settings


class AuthService:
    """认证服务类"""

    @staticmethod
    async def get_wx_openid(code: str, platform: str = 'miniapp') -> dict:
        """
        通过 code 换取 openid

        :param code: 微信登录码
        :param platform: 平台类型
        :return:
        """
        if platform == 'miniapp':
            appid = getattr(settings, 'WX_MINIAPP_APPID', '')
            secret = getattr(settings, 'WX_MINIAPP_SECRET', '')
        else:
            appid = getattr(settings, 'WX_H5_APPID', '')
            secret = getattr(settings, 'WX_H5_SECRET', '')

        if not appid or not secret:
            raise errors.ServerError(msg='微信配置缺失')

        url = 'https://api.weixin.qq.com/sns/jscode2session'
        params = {'appid': appid, 'secret': secret, 'js_code': code, 'grant_type': 'authorization_code'}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()

            if 'errcode' in data and data['errcode'] != 0:
                raise errors.AuthorizationError(msg=f"微信登录失败: {data.get('errmsg', '未知错误')}")

            return data

    @staticmethod
    async def decrypt_phone_number(session_key: str, encrypted_data: str, iv: str, platform: str = 'miniapp') -> str:
        """
        解密微信手机号

        :param session_key: 微信会话密钥
        :param encrypted_data: 加密数据
        :param iv: 初始向量
        :param platform: 平台类型
        :return: 手机号
        """
        if platform == 'miniapp':
            appid = getattr(settings, 'WX_MINIAPP_APPID', '')
        else:
            appid = getattr(settings, 'WX_H5_APPID', '')

        if not appid:
            raise errors.ServerError(msg='微信配置缺失')

        decrypt = WXBizDataCrypt(app_id=appid, session_key=session_key)
        phone_number = decrypt.decrypt_phone_number(encrypted_data=encrypted_data, iv=iv)

        return phone_number

    @staticmethod
    async def wx_login(
        *,
        db: AsyncSession,
        code: str,
        platform: str = 'miniapp',
        nickname: str | None = None,
        avatar: str | None = None,
        encrypted_data: str | None = None,
        iv: str | None = None,
    ) -> tuple[str, UserAccount]:
        """
        微信登录

        :param db: 数据库会话
        :param code: 微信登录码
        :param platform: 平台类型
        :param nickname: 昵称
        :param avatar: 头像
        :param encrypted_data: 加密的手机号数据
        :param iv: 初始向量
        :return:
        """
        wx_data = await AuthService.get_wx_openid(code, platform)

        openid = wx_data.get('openid')
        unionid = wx_data.get('unionid')
        session_key = wx_data.get('session_key')

        if not openid:
            raise errors.AuthorizationError(msg='获取 openid 失败')

        user = None
        if unionid:
            user = await user_account_dao.get_by_unionid(db, unionid)

        if not user:
            user = await user_account_dao.get_by_openid(db, openid)

        if user:
            # 用户已存在，更新 session_key
            await user_account_dao.update_session_key(db, user.id, session_key)

            # 如果前端提供了新的昵称或头像，则更新（仅当用户主动选择时才更新）
            if nickname and nickname != '微信用户':
                await user_account_dao.update_nickname(db, user.id, nickname)
                user.user.nickname = nickname
            if avatar:
                await user_account_dao.update_avatar(db, user.id, avatar)
                user.user.avatar = avatar
        else:
            user = await user_account_dao.create_wx_user(
                db=db,
                openid=openid,
                unionid=unionid,
                session_key=session_key,
                nickname=nickname or '微信用户',
                avatar=avatar,
                platform=platform,
            )

        # 解密并更新手机号（如果提供）
        if encrypted_data and iv:
            phone_number = await AuthService.decrypt_phone_number(
                session_key=session_key, encrypted_data=encrypted_data, iv=iv, platform=platform
            )
            await user_account_dao.update_phone(db, user.id, phone_number)

        # 重新加载用户（确保关联关系可用）
        user = await user_account_dao.get(db, user.id)

        # 使用统一 token 创建
        token_result = await create_unified_token(
            user_id=user.id,
            user_type='customer',
            multi_login=True,
            nickname=user.user.nickname,
            openid=openid,
        )

        return token_result.access_token, user

    @staticmethod
    async def test_login(*, db: AsyncSession, username: str = 'test_user', nickname: str = '测试用户') -> tuple[str, UserAccount]:
        """
        测试登录（仅用于开发测试）

        :param db: 数据库会话
        :param username: 用户名
        :param nickname: 昵称
        :return:
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from backend.app.admin.model import User

        # 通过 sys_user.username 查找关联的 UserAccount
        stmt = (
            select(UserAccount)
            .join(User, User.id == UserAccount.user_id)
            .where(User.username == username)
            .options(selectinload(UserAccount.user))
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            openid = f'test_openid_{username}'
            user = await user_account_dao.create_wx_user(
                db=db,
                openid=openid,
                unionid=None,
                session_key='test_session_key',
                nickname=nickname,
                avatar=None,
                platform='test',
                username=username,
            )
        else:
            openid = user.open_id or f'test_openid_{username}'

        # 使用统一 token 创建
        token_result = await create_unified_token(
            user_id=user.id,
            user_type='customer',
            multi_login=True,
            nickname=user.user.nickname,
            openid=openid,
        )

        return token_result.access_token, user


auth_service: AuthService = AuthService()
