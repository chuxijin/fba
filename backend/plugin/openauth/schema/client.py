#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开放平台客户端管理 schema（管理台用）"""

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, field_validator, model_validator

from backend.common.schema import SchemaBase


class OpenAuthClientBase(SchemaBase):
    """客户端基础字段"""

    name: str = Field(min_length=1, max_length=100, description='应用显示名称')
    description: str | None = Field(default=None, description='应用描述')
    icon: str | None = Field(default=None, description='应用图标 URL')
    scopes: list[str] = Field(default_factory=list, description='允许申请的权限列表')
    redirect_uris: list[str] = Field(default_factory=list, description='允许的回调地址列表')

    @field_validator('redirect_uris')
    @classmethod
    def validate_redirect_uris(cls, values: list[str]) -> list[str]:
        for value in values:
            uri = urlsplit(value)
            try:
                port = uri.port
            except ValueError as exc:
                raise ValueError('回调地址端口无效') from exc
            if (
                not uri.hostname
                or uri.username
                or uri.password
                or uri.fragment
                or any(c.isspace() for c in value)
                or '*' in value
                or '\\' in value
                or (
                    uri.scheme != 'https'
                    and not (uri.scheme == 'http' and uri.hostname in {'127.0.0.1', 'localhost', '::1'})
                )
                or port == 0
            ):
                raise ValueError('回调地址必须是 HTTPS 或本机 HTTP 地址，且不得包含通配符、凭据或片段')
        return list(dict.fromkeys(values))


class CreateOpenAuthClientParam(OpenAuthClientBase):
    """创建客户端参数

    client_secret 仅在创建响应中返回一次（服务端只存哈希）。
    """

    client_type: Literal['public', 'confidential'] = Field(default='confidential', description='CLI 使用 public')
    client_secret: str | None = Field(default=None, min_length=32, max_length=128, description='省略时服务端随机生成')

    @model_validator(mode='after')
    def validate_public_secret(self) -> 'CreateOpenAuthClientParam':
        if self.client_type == 'public' and self.client_secret is not None:
            raise ValueError('公开客户端不得设置共享密钥')
        return self


class UpdateOpenAuthClientParam(OpenAuthClientBase):
    """更新客户端参数"""

    status: Literal[0, 1] = Field(default=1, description='状态(0停用 1启用)')
    reset_secret: bool = Field(default=False, description='是否重置密钥')
    new_client_secret: str | None = Field(
        default=None,
        min_length=32,
        max_length=128,
        description='新密钥（reset_secret 时必填）',
    )


class GetOpenAuthClientDetail(OpenAuthClientBase):
    """客户端详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: str
    client_type: Literal['public', 'confidential']
    status: int
    created_time: datetime
    updated_time: datetime | None = None


class CreateOpenAuthClientDetail(GetOpenAuthClientDetail):
    """创建客户端响应：仅此场景返回明文密钥"""

    client_secret: str | None = Field(description='机密客户端密钥仅返回一次；公开客户端为 null')


class ResetOpenAuthSecretDetail(SchemaBase):
    """重置密钥响应"""

    client_id: str
    client_secret: str = Field(description='新密钥明文，仅返回一次')


class ResetOpenAuthSecretParam(SchemaBase):
    new_secret: str | None = Field(default=None, min_length=32, max_length=128, description='省略时随机生成新密钥')
