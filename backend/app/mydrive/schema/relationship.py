#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


class GetMyDriveRelationshipDetail(SchemaBase):
    """关系账户详情"""

    source_id: str = Field(description='好友 UK 或群组 ID')
    name: str = Field(description='显示名称')
    extra: dict[str, Any] = Field(default_factory=dict, description='扩展信息')


class GetMyDriveRelationshipShareDetail(SchemaBase):
    """关系分享详情"""

    source_id: str = Field(description='好友 UK 或群组 ID')
    from_uk: str = Field(description='分享者 UK')
    message_id: str = Field(description='分享消息 ID')
    root_id: str = Field(description='分享根文件 ID')
    name: str = Field(description='分享名称')
    is_directory: bool = Field(description='是否目录')
    size: int | None = Field(description='文件大小')
    extra: dict[str, Any] = Field(default_factory=dict, description='扩展信息')
