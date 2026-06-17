"""快速注册相关 Schema"""

import re
from pydantic import BaseModel, field_validator


class QuickRegisterParam(BaseModel):
    """快速注册参数"""

    phone: str

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """校验手机号格式"""
        if not v:
            raise ValueError('手机号不能为空')
        # 中国大陆手机号: 1开头，第二位3-9，共11位
        pattern = r'^1[3-9]\d{9}$'
        if not re.match(pattern, v):
            raise ValueError('手机号格式不正确')
        return v


class QuickRegisterResponse(BaseModel):
    """快速注册返回"""

    username: str
    password: str
    message: str = '注册成功'
