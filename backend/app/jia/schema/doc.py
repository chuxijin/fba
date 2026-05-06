#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

# ===================== Folder =====================


class FolderSchemaBase(SchemaBase):
    """文件夹基础模型"""

    name: str = Field(description='文件夹名称')
    parent_id: int | None = Field(None, description='父文件夹 ID')
    icon: str | None = Field(None, description='图标 emoji')
    sort_order: int = Field(default=0, description='排序序号')


class CreateFolderParam(FolderSchemaBase):
    """创建文件夹参数"""

    pass


class UpdateFolderParam(SchemaBase):
    """更新文件夹参数"""

    name: str | None = Field(None, description='文件夹名称')
    parent_id: int | None = Field(None, description='父文件夹 ID')
    icon: str | None = Field(None, description='图标 emoji')
    sort_order: int | None = Field(None, description='排序序号')


class GetFolderDetail(FolderSchemaBase):
    """文件夹详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='文件夹 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetFolderTree(SchemaBase):
    """文件夹树形结构"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='文件夹 ID')
    name: str = Field(description='文件夹名称')
    parent_id: int | None = Field(None, description='父文件夹 ID')
    icon: str | None = Field(None, description='图标 emoji')
    sort_order: int = Field(default=0, description='排序序号')
    children: list['GetFolderTree'] = Field(default_factory=list, description='子文件夹')


# ===================== Doc =====================


class DocSchemaBase(SchemaBase):
    """文档基础模型"""

    title: str = Field(default='未命名文档', description='文档标题')
    folder_id: int | None = Field(None, description='文件夹 ID')
    access_encrypted: bool = Field(default=False, description='访问加密')
    storage_encrypted: bool = Field(default=False, description='存储加密')
    is_pinned: bool = Field(default=False, description='是否置顶')
    cover_url: str | None = Field(None, description='封面图 URL')
    tags: list[str] | None = Field(None, description='标签列表')


class CreateDocParam(DocSchemaBase):
    """创建文档参数"""

    content: dict | None = Field(None, description='AppFlowy Editor JSON（明文）')
    access_password: str | None = Field(None, min_length=4, description='访问密码')
    meta: dict | None = Field(None, description='扩展元数据')


class UpdateDocParam(SchemaBase):
    """更新文档参数"""

    title: str | None = Field(None, description='文档标题')
    folder_id: int | None = Field(None, description='文件夹 ID')
    content: dict | None = Field(None, description='AppFlowy Editor JSON（明文）')
    access_encrypted: bool | None = Field(None, description='访问加密')
    access_password: str | None = Field(None, min_length=4, description='访问密码')
    storage_encrypted: bool | None = Field(None, description='存储加密')
    is_pinned: bool | None = Field(None, description='是否置顶')
    is_trashed: bool | None = Field(None, description='是否在回收站')
    cover_url: str | None = Field(None, description='封面图 URL')
    tags: list[str] | None = Field(None, description='标签列表')
    word_count: int | None = Field(None, description='字数统计')
    meta: dict | None = Field(None, description='扩展元数据')


class GetDocDetail(DocSchemaBase):
    """文档详情（含内容）"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='文档 ID')
    content: dict | None = Field(None, description='AppFlowy Editor JSON')
    is_trashed: bool = Field(description='是否在回收站')
    word_count: int = Field(description='字数统计')
    meta: dict | None = Field(None, description='扩展元数据')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetDocList(SchemaBase):
    """文档列表项（不含 content，轻量）"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='文档 ID')
    title: str = Field(description='文档标题')
    folder_id: int | None = Field(None, description='文件夹 ID')
    access_encrypted: bool = Field(description='访问加密')
    storage_encrypted: bool = Field(description='存储加密')
    is_pinned: bool = Field(description='是否置顶')
    is_trashed: bool = Field(description='是否在回收站')
    word_count: int = Field(description='字数统计')
    cover_url: str | None = Field(None, description='封面图 URL')
    tags: list[str] | None = Field(None, description='标签列表')
    content_preview: str | None = Field(None, description='内容预览（前100字）')
    updated_time: datetime | None = Field(None, description='更新时间')


class MoveDocParam(SchemaBase):
    """移动文档"""

    doc_ids: list[int] = Field(..., description='文档 ID 列表')
    target_folder_id: int | None = Field(None, description='目标文件夹 ID，None 表示根目录')


class DocAccessPasswordParam(SchemaBase):
    """文档访问密码验证参数"""

    password: str = Field(..., min_length=4, description='访问密码')


# ===================== Asset =====================


class AssetSchemaBase(SchemaBase):
    """资源基础模型"""

    file_name: str = Field(description='原始文件名')
    mime_type: str = Field(description='MIME 类型')


class CreateAssetParam(AssetSchemaBase):
    """创建资源参数（上传完成后调用）"""

    doc_id: int | None = Field(None, description='关联文档 ID')
    storage_path: str = Field(description='服务器存储路径')
    file_size: int = Field(default=0, ge=0, description='文件大小（字节）')
    file_hash: str | None = Field(None, description='文件 SHA256')
    meta: dict | None = Field(None, description='扩展信息（宽高、时长等）')


class UpdateAssetParam(SchemaBase):
    """更新资源参数"""

    doc_id: int | None = Field(None, description='关联文档 ID')
    file_name: str | None = Field(None, description='原始文件名')
    meta: dict | None = Field(None, description='扩展信息')


class GetAssetDetail(AssetSchemaBase):
    """资源详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='资源 ID')
    doc_id: int | None = Field(None, description='关联文档 ID')
    storage_path: str = Field(description='服务器存储路径')
    file_size: int = Field(description='文件大小（字节）')
    file_hash: str | None = Field(None, description='文件 SHA256')
    meta: dict | None = Field(None, description='扩展信息')
    created_time: datetime = Field(description='创建时间')
