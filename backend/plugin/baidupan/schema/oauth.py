#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field


class OAuthAuthorizeRequest(BaseModel):
    """授权请求参数"""

    client_id: str | None = Field(default=None, description='应用 AppKey，不传则使用默认配置')
    redirect_uri: str | None = Field(default=None, description='回调地址，不传则使用默认配置')
    device_id: str | None = Field(default=None, description='设备 ID（硬件厂商应用必填）')
    state: str | None = Field(default=None, description='自定义状态参数，用于 CSRF 防护')
    force_login: bool = Field(default=False, description='是否强制用户输入用户名密码')
    qrcode: bool = Field(default=False, description='是否启用二维码登录')


class OAuthAuthorizeResponse(BaseModel):
    """授权响应"""

    authorize_url: str = Field(..., description='授权跳转 URL')
    state: str = Field(..., description='状态参数，回调时需要校验')


class OAuthCallbackRequest(BaseModel):
    """回调请求参数"""

    code: str = Field(..., description='授权码')
    state: str | None = Field(default=None, description='状态参数')


class OAuthTokenResponse(BaseModel):
    """Token 响应"""

    access_token: str = Field(..., description='访问令牌')
    expires_in: int = Field(..., description='有效期（秒）')
    refresh_token: str = Field(..., description='刷新令牌')
    scope: str = Field(..., description='权限范围')
    token_type: str = Field(default='Bearer', description='令牌类型')


class OAuthRefreshRequest(BaseModel):
    """刷新 Token 请求参数"""

    refresh_token: str = Field(..., description='刷新令牌')
    client_id: str | None = Field(default=None, description='应用 AppKey，不传则使用默认配置')
    client_secret: str | None = Field(default=None, description='应用 SecretKey，不传则使用默认配置')


class BaiduApiError(BaseModel):
    """百度 API 错误响应"""

    error: str = Field(..., description='错误码')
    error_description: str = Field(..., description='错误描述')
