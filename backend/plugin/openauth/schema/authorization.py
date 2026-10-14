#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreateOpenAuthAuthorizationParam(SchemaBase):
    """用户同意授权参数（用户 JWT 鉴权后调用）"""

    client_id: str = Field(description='客户端标识')
    scopes: list[str] = Field(min_length=1, description='申请的权限列表')
    redirect_uri: str = Field(description='授权完成后的回调地址')
    state: str = Field(min_length=16, max_length=512, description='CLI 生成并在回调验证的随机 state')
    code_challenge: str = Field(pattern=r'^[A-Za-z0-9_-]{43}$', description='PKCE S256 challenge')
    code_challenge_method: Literal['S256'] = Field(default='S256', description='仅支持 S256')


class GetOpenAuthAuthorizationPreview(SchemaBase):
    """授权确认页预览数据（前端授权页渲染用）"""

    client_id: str
    name: str
    description: str | None = None
    icon: str | None = None
    scopes: list[str] = Field(description='本次申请的权限')
    already_authorized: bool = Field(description='是否已有生效授权（true 时前端可展示"已授权，一键放行"）')


class GetOpenAuthAuthorizationResult(SchemaBase):
    """授权完成结果：携带一次性 code 供 CLI 换取 token"""

    code: str = Field(description='一次性授权码，5 分钟有效')
    redirect_uri: str = Field(description='CLI 应重定向的回调地址（前端拼 code/state 后跳转）')
    state: str | None = Field(default=None, description='原样回传')
    expires_in: int = Field(description='code 有效秒数')


class CreateOpenAuthTokenParam(SchemaBase):
    """code 换 token 参数"""

    client_id: str = Field(description='客户端标识')
    client_secret: str | None = Field(default=None, description='机密客户端必填；公开 CLI 不携带共享密钥')
    code: str = Field(description='一次性授权码')
    redirect_uri: str = Field(description='必须与授权时一致')
    code_verifier: str = Field(pattern=r'^[A-Za-z0-9._~-]{43,128}$', description='PKCE verifier')


class GetOpenAuthTokenResult(SchemaBase):
    """token 响应"""

    access_token: str
    refresh_token: str
    token_type: str = Field(default='Bearer')
    expires_in: int = Field(description='access_token 有效秒数')


class CreateOpenAuthRefreshParam(SchemaBase):
    """刷新 token 参数"""

    client_id: str = Field(description='客户端标识')
    refresh_token: str = Field(description='刷新令牌')
    client_secret: str | None = Field(default=None, description='机密客户端刷新时必填')


class CreateOpenAuthRevokeParam(SchemaBase):
    """用户解绑整个应用（所有设备），单设备退出使用 logout"""

    model_config = ConfigDict(extra='forbid')
    client_id: str = Field(description='客户端标识')


class GetOpenAuthCheckResult(SchemaBase):
    """开放平台身份与 scope；不等同于业务权益或后台管理权限"""

    user_id: int
    client_id: str
    scopes: list[str] = Field(description='授权的权限列表')
    authorized: bool = Field(description='授权关系是否仍有效')
    expires_at: datetime = Field(description='access_token 过期时间')
    last_used_time: datetime | None = Field(default=None, description='最近使用时间')


class GetOpenAuthUserAuthorizationDetail(SchemaBase):
    """用户授权关系记录（管理端/用户侧查询）"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    client_id: int
    application_client_id: str = Field(description='用于解绑的公开客户端标识')
    application_name: str = Field(description='应用显示名称')
    scopes: list[str]
    status: str
    authorized_time: datetime | None = None
    last_used_time: datetime | None = None
    created_time: datetime
