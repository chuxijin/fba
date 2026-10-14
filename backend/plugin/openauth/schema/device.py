from pydantic import Field

from backend.common.schema import SchemaBase


class CreateOpenAuthDeviceRevokeParam(SchemaBase):
    ticket: str = Field(pattern=r'^[A-Za-z0-9_-]{43}$', description='一次性设备解绑凭证，仍需站内用户认证')


class GetOpenAuthDeviceRevokeTicket(SchemaBase):
    ticket: str = Field(description='用户确认页凭证，不可用于访问业务数据')
    expires_in: int = Field(description='凭证有效秒数')


class GetOpenAuthDeviceRevokePreview(SchemaBase):
    application_name: str = Field(description='应用名称')
    active: bool = Field(description='目标设备会话是否仍有效')
