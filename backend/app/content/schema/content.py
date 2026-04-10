from datetime import datetime
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


class ContentSchemaBase(SchemaBase):
    app_code: str = Field(..., description='应用标识')
    title: str = Field(..., description='标题')
    slug: str | None = Field(None, description='别名')
    summary: str | None = Field(None, description='摘要')
    cover_image: str | None = Field(None, description='封面图')
    category_id: int | None = Field(None, description='分类 ID')
    tags: list[str] | None = Field(None, description='标签')
    is_pinned: bool = Field(False, description='是否置顶')
    is_public: bool = Field(True, description='是否公开')
    is_published: bool = Field(False, description='是否发布')
    sort_order: int = Field(0, description='排序权重')
    extra: dict[str, Any] | None = Field(None, description='扩展数据')


class CreateContentParam(ContentSchemaBase):
    content_json: dict[str, Any] | None = Field(None, description='JSON 内容')
    content_html: str | None = Field(None, description='HTML 内容')


class UpdateContentParam(SchemaBase):
    title: str | None = Field(None, description='标题')
    slug: str | None = Field(None, description='别名')
    summary: str | None = Field(None, description='摘要')
    cover_image: str | None = Field(None, description='封面图')
    category_id: int | None = Field(None, description='分类 ID')
    tags: list[str] | None = Field(None, description='标签')
    content_json: dict[str, Any] | None = Field(None, description='JSON 内容')
    content_html: str | None = Field(None, description='HTML 内容')
    is_pinned: bool | None = Field(None, description='是否置顶')
    is_public: bool | None = Field(None, description='是否公开')
    is_published: bool | None = Field(None, description='是否发布')
    publish_time: datetime | None = Field(None, description='发布时间')
    sort_order: int | None = Field(None, description='排序权重')
    extra: dict[str, Any] | None = Field(None, description='扩展数据')


class GetContentDetail(ContentSchemaBase):
    id: int
    content_json: dict[str, Any] | None
    content_html: str | None
    view_count: int
    publish_time: datetime | None
    created_time: datetime
    updated_time: datetime | None


class GetContentListDetails(ContentSchemaBase):
    id: int
    view_count: int
    publish_time: datetime | None
    created_time: datetime
