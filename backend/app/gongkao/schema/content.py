from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class ContentSchemaBase(SchemaBase):
    """公考内容基础模型"""

    title: str = Field(description='标题')
    slug: str = Field(description='别名（固定链接标识）')
    content_json: dict | None = Field(None, description='Tiptap JSON 内容')
    content_html: str | None = Field(None, description='预渲染 HTML')
    summary: str | None = Field(None, description='摘要')
    cover_image: str | None = Field(None, description='封面图 URL')
    category_id: int | None = Field(None, description='关联分类 ID')
    tags: list[str] | None = Field(None, description='标签')
    is_pinned: bool = Field(default=False, description='是否置顶')
    is_public: bool = Field(default=True, description='是否公开')
    is_published: bool = Field(default=False, description='是否发布')
    publish_time: datetime | None = Field(None, description='发表时间')
    extra: dict | None = Field(None, description='元数据')


class ContentParam(SchemaBase):
    """公考内容查询参数"""

    title: str | None = Field(None, description='标题关键词')
    category_id: int | None = Field(None, description='分类 ID')
    tag: str | None = Field(None, description='标签')
    is_pinned: bool | None = Field(None, description='是否置顶')
    is_public: bool | None = Field(None, description='是否公开')
    is_published: bool | None = Field(None, description='是否发布')


class CreateContentParam(ContentSchemaBase):
    """创建公考内容参数"""


class UpdateContentParam(SchemaBase):
    """更新公考内容参数"""

    title: str | None = Field(None, description='标题')
    slug: str | None = Field(None, description='别名')
    content_json: dict | None = Field(None, description='Tiptap JSON 内容')
    content_html: str | None = Field(None, description='预渲染 HTML')
    summary: str | None = Field(None, description='摘要')
    cover_image: str | None = Field(None, description='封面图 URL')
    category_id: int | None = Field(None, description='关联分类 ID')
    tags: list[str] | None = Field(None, description='标签')
    is_pinned: bool | None = Field(None, description='是否置顶')
    is_public: bool | None = Field(None, description='是否公开')
    is_published: bool | None = Field(None, description='是否发布')
    publish_time: datetime | None = Field(None, description='发表时间')
    extra: dict | None = Field(None, description='元数据')
    sort_order: int | None = Field(None, description='排序权重')


class DeleteContentParam(SchemaBase):
    """批量删除公考内容参数"""

    ids: list[int] = Field(description='ID 列表')


class GetContentDetail(ContentSchemaBase):
    """公考内容详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    view_count: int = Field(description='浏览量')
    sort_order: int = Field(description='排序权重')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetContentListDetail(SchemaBase):
    """公考内容列表项（轻量版，不返回完整内容）"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    title: str = Field(description='标题')
    slug: str = Field(description='别名')
    summary: str | None = Field(None, description='摘要')
    cover_image: str | None = Field(None, description='封面图 URL')
    category_id: int | None = Field(None, description='关联分类 ID')
    tags: list[str] | None = Field(None, description='标签')
    is_pinned: bool = Field(description='是否置顶')
    is_public: bool = Field(description='是否公开')
    is_published: bool = Field(description='是否发布')
    publish_time: datetime | None = Field(None, description='发表时间')
    view_count: int = Field(description='浏览量')
    created_by: int = Field(description='创建者')
    created_time: datetime = Field(description='创建时间')
