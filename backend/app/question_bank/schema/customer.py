#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import BaseModel, ConfigDict, Field


class MembershipInfo(BaseModel):
    """会员权益信息"""

    category: int = Field(description='会员分类（0=全部 1=题库 2=词库...）')
    res_type: str = Field(description='资源类型（category/single）')
    res_id: int | None = Field(description='资源ID')
    end_time: str = Field(description='到期时间')
    remaining_days: int = Field(description='剩余天数')


class GetCustomerInfo(BaseModel):
    """获取用户信息响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='用户ID')
    username: str = Field(description='用户名')
    nickname: str = Field(description='昵称')
    avatar: str | None = Field(default=None, description='头像')
    is_vip: bool = Field(description='是否VIP')
    memberships: list[MembershipInfo] = Field(default_factory=list, description='会员权益列表')


class UpdateProfileParam(BaseModel):
    """更新用户资料请求"""

    nickname: str | None = Field(default=None, description='昵称')
    avatar: str | None = Field(default=None, description='头像URL')
