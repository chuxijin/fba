
from pydantic import Field

from backend.common.schema import SchemaBase

class UserSettingSchemaBase(SchemaBase):
    """用户设置基础模型"""
    
    theme: str = Field(default='system', description='主题模式')
    language: str = Field(default='zh-CN', description='语言偏好')
    copilot_provider: int | None = Field(default=None, description='默认Copilot供应商ID')
    copilot_model: str | None = Field(default='gpt-4o', description='默认Copilot模型')
    notifications: dict | None = Field(default={}, description='通知开关配置')
    extra_config: dict | None = Field(default={}, description='其他扩展配置')

class UpdateUserSettingParam(UserSettingSchemaBase):
    """更新用户设置参数"""
    pass

class GetUserSettingDetail(UserSettingSchemaBase):
    """获取用户设置详情"""
    
    id: int = Field(description='ID')
    user_id: int = Field(description='用户ID')
