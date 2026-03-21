#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model import User
from backend.app.auth.crud.crud_social_account import social_account_dao
from backend.app.auth.model.social_account import UserSocialAccount
from backend.app.auth.utils.wx_decrypt import WXBizDataCrypt
from backend.common.exception import errors
from backend.common.log import log
from backend.common.security.unified_token import create_unified_token
from backend.core.conf import settings


class UnifiedAuthService:
    """统一认证服务"""

    @staticmethod
    async def _get_wx_openid(code: str, platform: str = 'miniapp') -> dict:
        """
        通过 code 换取微信凭证

        :param code: 微信登录码
        :param platform: 平台类型
        :return:
        """
        if platform == 'miniapp':
            appid = getattr(settings, 'WX_MINIAPP_APPID', '')
            secret = getattr(settings, 'WX_MINIAPP_SECRET', '')
            url = 'https://api.weixin.qq.com/sns/jscode2session'
            params = {
                'appid': appid,
                'secret': secret,
                'js_code': code,
                'grant_type': 'authorization_code',
            }
        else:
            appid = getattr(settings, 'WX_H5_APPID', '')
            secret = getattr(settings, 'WX_H5_SECRET', '')
            url = 'https://api.weixin.qq.com/sns/oauth2/access_token'
            params = {
                'appid': appid,
                'secret': secret,
                'code': code,
                'grant_type': 'authorization_code',
            }

        if not appid or not secret:
            raise errors.ServerError(msg='微信配置缺失')

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()

            if 'errcode' in data and data['errcode'] != 0:
                raise errors.AuthorizationError(msg=f"微信登录失败: {data.get('errmsg', '未知错误')}")

            return data

    @staticmethod
    async def _decrypt_phone_number(
        session_key: str,
        encrypted_data: str,
        iv: str,
        platform: str = 'miniapp',
    ) -> str:
        """
        解密微信手机号

        :param session_key: 微信会话密钥
        :param encrypted_data: 加密数据
        :param iv: 初始向量
        :param platform: 平台类型
        :return:
        """
        if platform == 'miniapp':
            appid = getattr(settings, 'WX_MINIAPP_APPID', '')
        else:
            appid = getattr(settings, 'WX_H5_APPID', '')

        if not appid:
            raise errors.ServerError(msg='微信配置缺失')

        decrypt = WXBizDataCrypt(app_id=appid, session_key=session_key)
        return decrypt.decrypt_phone_number(encrypted_data=encrypted_data, iv=iv)

    @staticmethod
    async def _find_or_create_user(
        db: AsyncSession,
        *,
        openid: str,
        unionid: str | None,
        session_key: str | None,
        platform: str,
        nickname: str | None = None,
        avatar: str | None = None,
    ) -> tuple[UserSocialAccount, User]:
        """
        查找或创建用户（核心匹配逻辑，只操作 sys_user + sys_social_account）

        :param db: 数据库会话
        :param openid: 平台 openid
        :param unionid: 微信 unionid
        :param session_key: 小程序 session_key
        :param platform: 平台标识
        :param nickname: 昵称
        :param avatar: 头像
        :return:
        """
        social = None

        # 优先按 unionid 匹配（跨端识别）
        if unionid:
            social = await social_account_dao.get_by_unionid(db, unionid)

        # 再按 platform + openid 匹配
        if not social:
            social = await social_account_dao.get_by_openid(db, platform, openid)

        if social:
            # 已有绑定，更新 session_key
            if session_key and social.platform == platform:
                await social_account_dao.update_session_key(db, social.id, session_key)
                social.session_key = session_key

            # 如果是通过 unionid 匹配到的，但当前平台还没有绑定记录，补建一条
            if social.platform != platform:
                existing = await social_account_dao.get_by_openid(db, platform, openid)
                if not existing:
                    new_social = UserSocialAccount(
                        user_id=social.user_id,
                        platform=platform,
                        openid=openid,
                        unionid=unionid,
                        session_key=session_key,
                    )
                    db.add(new_social)
                    await db.flush()
                    social = new_social

            # 获取关联的 sys_user
            stmt = select(User).where(User.id == social.user_id)
            result = await db.execute(stmt)
            sys_user = result.scalar_one_or_none()
            if not sys_user:
                raise errors.ServerError(msg='用户数据异常')

            # 更新昵称和头像
            if nickname and nickname != '微信用户':
                sys_user.nickname = nickname
            if avatar:
                sys_user.avatar = avatar

            log.info(f'社交登录匹配成功: platform={platform}, user_id={social.user_id}')
            return social, sys_user

        # 没有匹配，创建新用户
        username = f'wx_{uuid.uuid4().hex[:12]}'

        sys_user = User(
            username=username,
            nickname=nickname or '微信用户',
            avatar=avatar,
            status=1,
        )
        db.add(sys_user)
        await db.flush()

        social = UserSocialAccount(
            user_id=sys_user.id,
            platform=platform,
            openid=openid,
            unionid=unionid,
            session_key=session_key,
        )
        db.add(social)
        await db.flush()

        log.info(f'社交登录新用户: platform={platform}, user_id={sys_user.id}, username={username}')
        return social, sys_user

    async def wx_login(
        self,
        *,
        db: AsyncSession,
        code: str,
        platform: str = 'miniapp',
        nickname: str | None = None,
        avatar: str | None = None,
        encrypted_data: str | None = None,
        iv: str | None = None,
    ) -> tuple[str, User, UserSocialAccount]:
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
        wx_data = await self._get_wx_openid(code, platform)

        openid = wx_data.get('openid')
        unionid = wx_data.get('unionid')
        session_key = wx_data.get('session_key')

        if not openid:
            raise errors.AuthorizationError(msg='获取 openid 失败')

        platform_key = f'wechat_{platform}' if not platform.startswith('wechat_') else platform

        social, sys_user = await self._find_or_create_user(
            db,
            openid=openid,
            unionid=unionid,
            session_key=session_key,
            platform=platform_key,
            nickname=nickname,
            avatar=avatar,
        )

        # 解密并更新手机号
        if encrypted_data and iv and session_key:
            phone_number = await self._decrypt_phone_number(
                session_key=session_key,
                encrypted_data=encrypted_data,
                iv=iv,
                platform=platform,
            )
            sys_user.phone = phone_number

        # 签发统一 Token（使用 sys_user.id）
        token_result = await create_unified_token(
            user_id=sys_user.id,
            user_type='customer',
            multi_login=True,
            nickname=sys_user.nickname,
            openid=openid,
        )

        return token_result.access_token, sys_user, social

    async def test_login(
        self,
        *,
        db: AsyncSession,
        username: str = 'test_user',
        nickname: str = '测试用户',
    ) -> tuple[str, User, UserSocialAccount | None]:
        """
        测试登录（仅用于开发测试）

        :param db: 数据库会话
        :param username: 用户名
        :param nickname: 昵称
        :return:
        """
        # 通过 sys_user.username 查找
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        sys_user = result.scalar_one_or_none()

        social = None
        if not sys_user:
            openid = f'test_openid_{username}'
            social, sys_user = await self._find_or_create_user(
                db,
                openid=openid,
                unionid=None,
                session_key='test_session_key',
                platform='test',
                nickname=nickname,
            )
        else:
            # 查找已有的 social 绑定
            socials = await social_account_dao.get_by_user_id(db, sys_user.id)
            social = socials[0] if socials else None

        openid = social.openid if social else f'test_openid_{username}'

        token_result = await create_unified_token(
            user_id=sys_user.id,
            user_type='customer',
            multi_login=True,
            nickname=sys_user.nickname,
            openid=openid,
        )

        return token_result.access_token, sys_user, social

    @staticmethod
    async def get_user_openid(
        db: AsyncSession, user_id: int, platform: str = 'wechat_miniapp'
    ) -> str | None:
        """
        获取用户在指定平台的 openid（供支付等场景使用）

        :param db: 数据库会话
        :param user_id: sys_user.id
        :param platform: 平台标识
        :return:
        """
        return await social_account_dao.get_user_openid(db, user_id, platform)


unified_auth_service: UnifiedAuthService = UnifiedAuthService()
