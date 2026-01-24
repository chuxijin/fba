#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import secrets
from urllib.parse import urlencode

import httpx

from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.database.redis import redis_client
from backend.plugin.baidupan.schema.oauth import (
    BaiduApiError,
    OAuthAuthorizeRequest,
    OAuthAuthorizeResponse,
    OAuthRefreshRequest,
    OAuthTokenResponse,
)


class BaiduPanOAuthService:
    """百度网盘 OAuth 服务"""

    # 百度 OAuth 端点
    AUTHORIZE_URL = 'https://openapi.baidu.com/oauth/2.0/authorize'
    TOKEN_URL = 'https://openapi.baidu.com/oauth/2.0/token'

    # Redis 状态缓存前缀
    STATE_REDIS_PREFIX = 'fba:baidupan:oauth:state'
    STATE_EXPIRE_SECONDS = 60 * 10  # 10 分钟

    async def generate_authorize_url(self, request: OAuthAuthorizeRequest) -> OAuthAuthorizeResponse:
        """
        生成授权跳转 URL

        :param request: 授权请求参数
        :return:
        """
        client_id = request.client_id or settings.BAIDUPAN_APP_KEY
        redirect_uri = request.redirect_uri or settings.BAIDUPAN_REDIRECT_URI

        if not client_id:
            raise errors.ForbiddenError(msg='百度网盘 AppKey 未配置')

        if not redirect_uri:
            raise errors.ForbiddenError(msg='百度网盘回调地址未配置')

        # 生成随机 state 用于 CSRF 防护
        state = request.state or secrets.token_urlsafe(32)

        # 将 state 存入 Redis，用于回调时校验
        await redis_client.set(
            f'{self.STATE_REDIS_PREFIX}:{state}',
            '1',
            ex=self.STATE_EXPIRE_SECONDS,
        )

        params = {
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': 'basic,netdisk',
            'state': state,
        }

        # 可选参数
        if request.device_id:
            params['device_id'] = request.device_id
        if request.force_login:
            params['force_login'] = '1'
        if request.qrcode:
            params['qrcode'] = '1'

        authorize_url = f'{self.AUTHORIZE_URL}?{urlencode(params)}'

        log.info(f'生成百度网盘授权 URL: {authorize_url}')

        return OAuthAuthorizeResponse(authorize_url=authorize_url, state=state)

    async def handle_callback(
        self,
        code: str,
        state: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
    ) -> OAuthTokenResponse:
        """
        处理授权回调，换取 access_token

        :param code: 授权码
        :param state: 状态参数
        :param client_id: 应用 AppKey
        :param client_secret: 应用 SecretKey
        :param redirect_uri: 回调地址
        :return:
        """
        # 校验 state（如果提供）
        if state:
            state_key = f'{self.STATE_REDIS_PREFIX}:{state}'
            state_exists = await redis_client.get(state_key)
            if not state_exists:
                raise errors.AuthorizationError(msg='state 参数无效或已过期')
            # 删除已使用的 state
            await redis_client.delete(state_key)

        client_id = client_id or settings.BAIDUPAN_APP_KEY
        client_secret = client_secret or settings.BAIDUPAN_SECRET_KEY
        redirect_uri = redirect_uri or settings.BAIDUPAN_REDIRECT_URI

        if not client_id or not client_secret:
            raise errors.ForbiddenError(msg='百度网盘 AppKey 或 SecretKey 未配置')

        if not redirect_uri:
            raise errors.ForbiddenError(msg='百度网盘回调地址未配置')

        params = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
        }

        log.info(f'百度网盘 OAuth 回调，正在换取 token，code: {code[:10]}...')

        async with httpx.AsyncClient(timeout=settings.HTTP_REQUEST_TIMEOUT) as client:
            response = await client.get(self.TOKEN_URL, params=params)
            data = response.json()

        # 检查是否有错误
        if 'error' in data:
            error_info = BaiduApiError.model_validate(data)
            log.error(f'百度网盘 OAuth 换取 token 失败: {error_info.error} - {error_info.error_description}')
            raise errors.AuthorizationError(msg=f'授权失败: {error_info.error_description}')

        log.info('百度网盘 OAuth 换取 token 成功')

        return OAuthTokenResponse(
            access_token=data['access_token'],
            expires_in=data['expires_in'],
            refresh_token=data['refresh_token'],
            scope=data['scope'],
        )

    async def refresh_token(self, request: OAuthRefreshRequest) -> OAuthTokenResponse:
        """
        刷新 access_token

        :param request: 刷新请求参数
        :return:
        """
        client_id = request.client_id or settings.BAIDUPAN_APP_KEY
        client_secret = request.client_secret or settings.BAIDUPAN_SECRET_KEY

        if not client_id or not client_secret:
            raise errors.ForbiddenError(msg='百度网盘 AppKey 或 SecretKey 未配置')

        params = {
            'grant_type': 'refresh_token',
            'refresh_token': request.refresh_token,
            'client_id': client_id,
            'client_secret': client_secret,
        }

        log.info('百度网盘 OAuth 正在刷新 token...')

        async with httpx.AsyncClient(timeout=settings.HTTP_REQUEST_TIMEOUT) as client:
            response = await client.get(self.TOKEN_URL, params=params)
            data = response.json()

        # 检查是否有错误
        if 'error' in data:
            error_info = BaiduApiError.model_validate(data)
            log.error(f'百度网盘 OAuth 刷新 token 失败: {error_info.error} - {error_info.error_description}')
            raise errors.AuthorizationError(msg=f'刷新失败: {error_info.error_description}')

        log.info('百度网盘 OAuth 刷新 token 成功')

        return OAuthTokenResponse(
            access_token=data['access_token'],
            expires_in=data['expires_in'],
            refresh_token=data['refresh_token'],
            scope=data['scope'],
        )


baidupan_oauth_service = BaiduPanOAuthService()
