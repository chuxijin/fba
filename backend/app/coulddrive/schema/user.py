#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Union
from pydantic import ConfigDict, Field

from backend.app.coulddrive.service.utils_service import human_size
from backend.common.schema import SchemaBase


class BaseUserInfo(SchemaBase):
    """用户信息"""
    
    model_config = ConfigDict(from_attributes=True)
    
    user_id: str = Field("", description="用户ID")
    username: str = Field("", description="用户名")
    avatar_url: str | None = Field(None, description="头像URL")
    quota: int | None = Field(None, description="总空间配额")
    used: int | None = Field(None, description="已使用空间")
    is_vip: bool | None = Field(None, description="是否VIP用户")
    is_supervip: bool | None = Field(None, description="是否超级会员")

    @property
    def formatted_quota(self) -> str:
        """格式化的总空间配额"""
        return human_size(self.quota) if self.quota is not None else "未知"
    
    @property
    def formatted_used(self) -> str:
        """格式化的已使用空间"""
        return human_size(self.used) if self.used is not None else "未知"
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"BaseUserInfo(user_id='{self.user_id}', username='{self.username}')"


class GetUserFriendDetail(SchemaBase):
    """用户好友详情"""
    
    model_config = ConfigDict(from_attributes=True)
    
    uk: int = Field(..., description="用户ID")
    uname: str = Field(..., description="用户名")
    nick_name: str = Field(..., description="昵称")
    avatar_url: str = Field(..., description="头像URL")
    is_friend: int = Field(..., description="好友关系")


class GetUserGroupDetail(SchemaBase):
    """用户群组详情"""
    
    model_config = ConfigDict(from_attributes=True)
    
    gid: str = Field(..., description="群组ID")
    gnum: str = Field(..., description="群号")
    name: str = Field(..., description="群名称")
    type: str = Field(..., description="群类型")
    status: str = Field(..., description="群状态")


class DriveAccountBase(BaseUserInfo):
    """网盘账户基础"""
    
    type: str = Field(..., description="网盘类型")
    cookies: str | None = Field(None, description="登录凭证")
    is_valid: bool = Field(True, description="账号是否有效")


class CreateDriveAccountParam(DriveAccountBase):
    """创建网盘账户参数"""
    pass


class UpdateDriveAccountParam(SchemaBase):
    """更新网盘账户参数"""
    
    username: str | None = Field(None, description="用户名")
    cookies: str | None = Field(None, description="登录凭证")
    avatar_url: str | None = Field(None, description="头像URL")
    quota: int | None = Field(None, description="总空间配额")
    used: int | None = Field(None, description="已使用空间")
    is_vip: bool | None = Field(None, description="是否VIP用户")
    is_supervip: bool | None = Field(None, description="是否超级会员")
    is_valid: bool | None = Field(None, description="账号是否有效")


class GetDriveAccountDetail(DriveAccountBase):
    """网盘账户详情"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="主键ID")
    created_time: str = Field(..., description="创建时间")
    updated_time: str = Field(..., description="更新时间")


# 关系列表响应类型（好友或群组）
RelationshipItem = Union[GetUserFriendDetail, GetUserGroupDetail]