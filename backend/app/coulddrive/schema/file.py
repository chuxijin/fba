#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional
from enum import Enum

from pydantic import ConfigDict, Field, field_validator

from backend.app.coulddrive.schema.enum import ItemType, MatchMode, MatchTarget, RecursionSpeed, DriveType
from backend.common.schema import SchemaBase


class BaseFileInfo(SchemaBase):
    """文件信息"""
    
    model_config = ConfigDict(from_attributes=True)
    
    file_id: str = Field(..., description="文件唯一ID")
    file_name: str = Field(..., description="文件名称")
    file_path: str = Field(..., description="文件路径")
    is_folder: bool = Field(False, description="是否为文件夹")
    file_size: int | None = Field(None, description="文件大小")
    parent_id: str | None = Field("", description="父目录ID")
    created_at: str | None = Field("", description="创建时间")
    updated_at: str | None = Field("", description="更新时间")
    file_ext: dict[str, Any] = Field(default_factory=dict, description="扩展信息")

    @property
    def filename(self) -> str:
        """获取文件名"""
        return os.path.basename(self.file_name)

    def __repr__(self) -> str:
        """字符串表示"""
        if self.is_folder:
            return f"BaseFileInfo(file_id='{self.file_id}', file_name='{self.file_name}', folder=True)"
        else:
            return f"BaseFileInfo(file_id='{self.file_id}', file_name='{self.file_name}', file_size={self.file_size})"


class BaseShareInfo(SchemaBase):
    """分享信息"""
    
    share_id: str = Field("", description="分享ID")
    title: str = Field("", description="分享标题")
    share_url: str = Field("", description="分享链接")
    created_at: datetime | None = Field(None, description="创建时间")


class ExclusionRuleDefinition(SchemaBase):
    """排除规则"""
    
    pattern: str = Field(..., description="匹配模式")
    target: MatchTarget = Field(MatchTarget.NAME, description="匹配目标")
    item_type: ItemType = Field(ItemType.ANY, description="项目类型")
    mode: MatchMode = Field(MatchMode.CONTAINS, description="匹配模式")
    case_sensitive: bool = Field(False, description="是否区分大小写")


class RenameRuleDefinition(SchemaBase):
    """重命名规则"""
    
    match_regex: str = Field(..., description="匹配正则")
    replace_string: str = Field(..., description="替换字符串")
    target_scope: MatchTarget = Field(MatchTarget.NAME, description="目标范围")
    case_sensitive: bool = Field(False, description="是否区分大小写")


class ShareSourceDefinition(SchemaBase):
    """分享源定义"""
    
    file_path: str = Field(..., description="分享内部路径")
    source_type: str = Field(..., description="分享来源类型")
    source_id: str = Field(..., description="分享来源ID")
    ext_params: dict[str, Any] = Field(default_factory=dict, description="扩展参数")

    @field_validator('source_type')
    @classmethod
    def check_share_source_type(cls, v: str) -> str:
        """验证分享来源类型"""
        if v not in ['friend', 'group', 'link']:
            raise ValueError("分享来源类型必须是 'friend' 或 'group' 或 'link'")
        return v


class DiskTargetDefinition(SchemaBase):
    """磁盘目标定义"""
    
    file_path: str = Field(..., description="用户云盘路径")
    file_id: str = Field(..., description="文件ID")

    @field_validator('file_path')
    @classmethod
    def check_disk_file_path(cls, v: str) -> str:
        """验证磁盘文件路径"""
        if not v:
            raise ValueError("用户云盘路径不能为空")
        if not v.startswith("/"):
            raise ValueError("用户云盘路径必须以 '/' 开头")
        return v


class CompareParam(SchemaBase):
    """比较参数"""
    
    drive_type: DriveType = Field(..., description="网盘类型")
    recursive: bool = Field(False, description="是否递归")
    recursion_speed: RecursionSpeed = Field(RecursionSpeed.NORMAL, description="递归速度")
    source_definition: ShareSourceDefinition = Field(..., description="源定义")
    target_definition: DiskTargetDefinition = Field(..., description="目标定义")
    comparison_mode: str = Field("incremental", description="对比模式")
    exclude_rules: list[ExclusionRuleDefinition] | None = Field(None, description="排除规则")
    rename_rules: list[RenameRuleDefinition] | None = Field(None, description="重命名规则")


class GetCompareDetail(SchemaBase):
    """比较结果详情"""
    
    model_config = ConfigDict(from_attributes=True)
    
    drive_type: DriveType = Field(..., description="网盘类型")
    source_list_time: float = Field(..., description="源列表耗时")
    target_list_time: float = Field(..., description="目标列表耗时")
    source_list_num: int = Field(..., description="源列表文件数")
    target_list_num: int = Field(..., description="目标列表文件数")
    to_add: list[dict[str, Any]] = Field(..., description="需要添加的文件，包含source_item、target_full_path、target_parent_path等信息")
    to_update_in_target: list[dict[str, BaseFileInfo]] = Field(..., description="需要更新的文件")
    to_delete_from_target: list[BaseFileInfo] = Field(..., description="需要删除的文件")
    to_rename_in_target: list[dict[str, Any]] = Field(..., description="需要重命名的文件")
    source_definition: ShareSourceDefinition = Field(..., description="源定义")
    target_definition: DiskTargetDefinition = Field(..., description="目标定义")


class ListFilesParam(SchemaBase):
    """文件列表查询参数"""
    
    drive_type: DriveType = Field(..., description="网盘类型")
    file_path: Optional[str] = Field("/", description="文件路径，默认为根目录")
    file_id: Optional[str] = Field("", description="文件ID")
    recursive: bool = Field(False, description="是否递归获取子目录")
    desc: bool = Field(False, description="是否按降序排序")
    name: bool = Field(False, description="是否按名称排序")
    time: bool = Field(False, description="是否按时间排序")
    size_sort: bool = Field(False, description="是否按大小排序")
    recursion_speed: RecursionSpeed = Field(RecursionSpeed.NORMAL, description="递归速度")
    exclude_rules: str | None = Field(None, description="排除规则JSON")


class ListShareFilesParam(SchemaBase):
    """分享文件列表参数"""
    
    drive_type: DriveType = Field(..., description="网盘类型")
    source_type: str = Field(..., description="分享来源类型")
    source_id: str = Field(..., description="分享来源ID")
    file_path: str = Field(..., description="分享内部路径")
    recursive: bool = Field(False, description="是否递归")
    recursion_speed: RecursionSpeed = Field(RecursionSpeed.NORMAL, description="递归速度")
    exclude_rules: str | None = Field(None, description="排除规则JSON")


class MkdirParam(SchemaBase):
    """创建文件夹参数"""
    
    drive_type: DriveType = Field(..., description="网盘类型")
    file_path: str = Field(..., description="文件夹路径")
    parent_id: str | None = Field(None, description="父文件夹ID")
    file_name: str | None = Field(None, description="文件夹名称")
    return_if_exist: bool = Field(True, description="存在时是否返回")


class RemoveParam(SchemaBase):
    """删除参数"""
    
    drive_type: DriveType = Field(..., description="网盘类型")
    file_paths: str | list[str] | None = Field(None, description="文件路径")
    file_ids: str | list[str] | None = Field(None, description="文件ID")
    parent_id: str | None = Field(None, description="父目录ID")
    file_name: str | None = Field(None, description="文件名称")


class TransferParam(SchemaBase):
    """转存参数"""
    
    drive_type: DriveType = Field(..., description="网盘类型")
    source_type: str = Field(..., description="来源类型")
    source_id: str = Field(..., description="来源ID")
    source_path: str = Field(..., description="源路径")
    target_path: str = Field(..., description="目标路径")
    target_id: str | None = Field(None, description="目标目录ID（夸克网盘专用）")
    file_ids: list[int | str] | None = Field(None, description="文件ID列表")
    ext: dict[str, Any] | None = Field(default_factory=dict, description="扩展参数")

    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        """验证来源类型"""
        if v not in ['link', 'friend', 'group']:
            raise ValueError("source_type 必须是 'link', 'friend' 或 'group' 之一")
        return v

    @field_validator('target_path')
    @classmethod
    def validate_target_path(cls, v: str) -> str:
        """验证目标路径"""
        if not v:
            raise ValueError("目标路径不能为空")
        if not v.startswith("/"):
            raise ValueError("目标路径必须以 '/' 开头")
        return v


class RelationshipType(str, Enum):
    """关系类型枚举"""
    FRIEND = "friend"
    GROUP = "group"


class RelationshipParam(SchemaBase):
    """关系查询参数"""
    
    drive_type: DriveType = Field(..., description="网盘类型")
    relationship_type: RelationshipType = Field(..., description="关系类型：friend(好友) 或 group(群组)")


class UserInfoParam(SchemaBase):
    """用户信息查询参数"""
    
    drive_type: DriveType = Field(..., description="网盘类型")


def get_filepath(
    filedir: str | None = None,
    filename: str | None = None,
    filepath: str | None = None,
) -> str | None:
    """
    获取文件完整路径
    
    :param filedir: 文件目录路径
    :param filename: 文件名
    :param filepath: 完整的文件路径
    :return: 文件的完整路径
    """
    if filepath is not None:
        return filepath
    elif filedir is not None and filename is not None:
        return os.path.join(filedir, filename)
        
    return None