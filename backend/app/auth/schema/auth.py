#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class WxLoginParam(SchemaBase):
    """微信登录参数"""

    code: str = Field(description='微信登录码')
    platform: str = Field(default='miniapp', description='平台类型(miniapp/h5/mp)')
    nickname: str | None = Field(default=None, description='昵称')
    avatar: str | None = Field(default=None, description='头像')
    encrypted_data: str | None = Field(default=None, description='加密的手机号数据')
    iv: str | None = Field(default=None, description='初始向量')


class TestLoginParam(SchemaBase):
    """测试登录参数"""

    username: str = Field(default='test_user', description='用户名')
    nickname: str = Field(default='测试用户', description='昵称')


class GetAuthUserDetail(SchemaBase):
    """用户信息详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='用户 ID')
    username: str | None = Field(default=None, description='用户名')
    nickname: str | None = Field(default=None, description='昵称')
    avatar: str | None = Field(default=None, description='头像')
    phone: str | None = Field(default=None, description='手机号')
    open_id: str | None = Field(default=None, description='微信 OpenID')
    status: int = Field(description='状态')


class LoginResponse(SchemaBase):
    """登录响应"""

    access_token: str = Field(description='访问令牌')
    user_info: GetAuthUserDetail = Field(description='用户信息')


class GetSocialAccountBrief(SchemaBase):
    """社交绑定简要"""

    model_config = ConfigDict(from_attributes=True)

    platform: str = Field(description='平台标识')
    openid: str | None = Field(default=None, description='平台 OpenID')
    status: int = Field(description='状态')
    created_time: datetime = Field(description='绑定时间')
