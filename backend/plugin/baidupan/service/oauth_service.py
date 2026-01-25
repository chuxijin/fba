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

    @staticmethod
    def generate_result_html(
        success: bool,
        title: str,
        data: OAuthTokenResponse | None = None,
        error: str | None = None,
    ) -> str:
        """
        生成 OAuth 回调结果 HTML 页面

        :param success: 是否成功
        :param title: 页面标题
        :param data: 成功时的 Token 数据
        :param error: 失败时的错误信息
        :return:
        """
        if success and data:
            token_info = f"""
            <div class="token-card">
                <div class="token-item">
                    <label>Access Token</label>
                    <div class="token-value" id="access_token">{data.access_token}</div>
                    <button onclick="copyToken('access_token')">复制</button>
                </div>
                <div class="token-item">
                    <label>Refresh Token</label>
                    <div class="token-value" id="refresh_token">{data.refresh_token}</div>
                    <button onclick="copyToken('refresh_token')">复制</button>
                </div>
                <div class="token-item">
                    <label>有效期</label>
                    <div class="token-value">{data.expires_in} 秒 ({data.expires_in // 86400} 天)</div>
                </div>
                <div class="token-item">
                    <label>权限范围</label>
                    <div class="token-value">{data.scope}</div>
                </div>
            </div>
            """
            status_icon = "✅"
            status_class = "success"
        else:
            token_info = f"""
            <div class="error-card">
                <p>{error or '未知错误'}</p>
            </div>
            """
            status_icon = "❌"
            status_class = "error"

        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                }}
                .container {{
                    background: white;
                    border-radius: 16px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    padding: 40px;
                    max-width: 600px;
                    width: 100%;
                }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .header h1 {{ font-size: 24px; color: #333; margin-bottom: 10px; }}
                .status {{ font-size: 48px; margin-bottom: 10px; }}
                .status.success {{ color: #10b981; }}
                .status.error {{ color: #ef4444; }}
                .token-card {{ background: #f8fafc; border-radius: 12px; padding: 20px; }}
                .token-item {{
                    margin-bottom: 20px;
                    padding-bottom: 20px;
                    border-bottom: 1px solid #e2e8f0;
                }}
                .token-item:last-child {{ margin-bottom: 0; padding-bottom: 0; border-bottom: none; }}
                .token-item label {{
                    display: block;
                    font-size: 12px;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    margin-bottom: 8px;
                }}
                .token-value {{
                    font-family: 'Monaco', 'Menlo', monospace;
                    font-size: 13px;
                    color: #334155;
                    word-break: break-all;
                    background: #fff;
                    padding: 12px;
                    border-radius: 8px;
                    border: 1px solid #e2e8f0;
                    margin-bottom: 8px;
                }}
                button {{
                    background: #3b82f6;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 14px;
                    transition: background 0.2s;
                }}
                button:hover {{ background: #2563eb; }}
                button:active {{ transform: scale(0.98); }}
                .error-card {{
                    background: #fef2f2;
                    border: 1px solid #fecaca;
                    border-radius: 12px;
                    padding: 20px;
                    color: #dc2626;
                }}
                .footer {{ text-align: center; margin-top: 30px; color: #94a3b8; font-size: 14px; }}
                .toast {{
                    position: fixed;
                    bottom: 20px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: #1e293b;
                    color: white;
                    padding: 12px 24px;
                    border-radius: 8px;
                    opacity: 0;
                    transition: opacity 0.3s;
                }}
                .toast.show {{ opacity: 1; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="status {status_class}">{status_icon}</div>
                    <h1>{title}</h1>
                </div>
                {token_info}
                <div class="footer">百度网盘 OAuth 授权服务</div>
            </div>
            <div class="toast" id="toast">已复制到剪贴板</div>
            <script>
                function copyToken(elementId) {{
                    const text = document.getElementById(elementId).innerText;
                    navigator.clipboard.writeText(text).then(() => {{
                        const toast = document.getElementById('toast');
                        toast.classList.add('show');
                        setTimeout(() => toast.classList.remove('show'), 2000);
                    }});
                }}
            </script>
        </body>
        </html>
        """


baidupan_oauth_service = BaiduPanOAuthService()
