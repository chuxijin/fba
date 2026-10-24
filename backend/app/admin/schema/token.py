from datetime import datetime

from pydantic import Field

from backend.app.admin.schema.user import GetUserInfoDetail
from backend.common.enums import StatusType
from backend.common.schema import SchemaBase
from backend.common.security.client import LoginClientType


class GetSwaggerToken(SchemaBase):
    """Swagger 认证令牌"""

    access_token: str = Field(description='访问令牌')
    token_type: str = Field('Bearer', description='令牌类型')
    user: GetUserInfoDetail = Field(description='用户信息')


class AccessTokenBase(SchemaBase):
    """访问令牌基础模型"""

    access_token: str = Field(description='访问令牌')
    access_token_expire_time: datetime = Field(description='令牌过期时间')
    session_uuid: str = Field(description='会话 UUID')
    client_type: LoginClientType = Field(description='登录客户端类型')
    refresh_token: str | None = Field(None, repr=False, description='仅插件端返回，浏览器端使用 HttpOnly Cookie')


class RefreshTokenParam(SchemaBase):
    """插件端通过请求体提交刷新凭据，浏览器与小程序使用各端 Cookie。"""

    refresh_token: str | None = Field(None, min_length=1, max_length=16384, repr=False)


class GetNewToken(AccessTokenBase):
    """获取新令牌"""


class GetLoginToken(AccessTokenBase):
    """获取登录令牌"""

    password_expire_days_remaining: int | None = Field(None, description='密码过期剩余天数')
    user: GetUserInfoDetail = Field(description='用户信息')


class GetTokenDetail(SchemaBase):
    """令牌详情"""

    id: int = Field(description='用户 ID')
    session_uuid: str = Field(description='会话 UUID')
    client_type: LoginClientType | None = Field(None, description='客户端类型，空值表示旧版会话')
    username: str = Field(description='用户名')
    nickname: str = Field(description='昵称')
    ip: str = Field(description='IP 地址')
    os: str = Field(description='操作系统')
    browser: str = Field(description='浏览器')
    device: str = Field(description='设备')
    status: StatusType = Field(description='状态')
    last_login_time: str = Field(description='最后登录时间')
    expire_time: datetime = Field(description='过期时间')
