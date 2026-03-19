from datetime import date, datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class ContentSchemaBase(SchemaBase):
    """Content base."""

    title: str = Field(description='title')
    slug: str = Field(description='slug')
    content_json: dict | None = Field(None, description='tiptap json content')
    content_html: str | None = Field(None, description='render html content')
    summary: str | None = Field(None, description='summary')
    cover_image: str | None = Field(None, description='cover image url')
    category_id: int | None = Field(None, description='category id')
    tags: list[str] | None = Field(None, description='tags')
    is_pinned: bool = Field(default=False, description='is pinned')
    is_public: bool = Field(default=True, description='is public')
    is_published: bool = Field(default=False, description='is published')
    publish_time: datetime | None = Field(None, description='publish time')
    extra: dict | None = Field(None, description='extra metadata')


class ContentParam(SchemaBase):
    """Content query."""

    title: str | None = Field(None, description='title keyword')
    category_id: int | None = Field(None, description='category id')
    category_ids: list[int] | None = Field(None, description='category ids')
    tag: str | None = Field(None, description='tag')
    is_pinned: bool | None = Field(None, description='is pinned')
    is_public: bool | None = Field(None, description='is public')
    is_published: bool | None = Field(None, description='is published')
    content_type: str | None = Field(None, description='content type in extra')
    daily_date: date | None = Field(None, description='daily date in extra')


class CreateContentParam(ContentSchemaBase):
    """Create content."""


class UpdateContentParam(SchemaBase):
    """Update content."""

    title: str | None = Field(None, description='title')
    slug: str | None = Field(None, description='slug')
    content_json: dict | None = Field(None, description='tiptap json content')
    content_html: str | None = Field(None, description='render html content')
    summary: str | None = Field(None, description='summary')
    cover_image: str | None = Field(None, description='cover image url')
    category_id: int | None = Field(None, description='category id')
    tags: list[str] | None = Field(None, description='tags')
    is_pinned: bool | None = Field(None, description='is pinned')
    is_public: bool | None = Field(None, description='is public')
    is_published: bool | None = Field(None, description='is published')
    publish_time: datetime | None = Field(None, description='publish time')
    extra: dict | None = Field(None, description='extra metadata')
    sort_order: int | None = Field(None, description='sort order')


class DeleteContentParam(SchemaBase):
    """Delete content."""

    ids: list[int] = Field(description='id list')


class GetContentDetail(ContentSchemaBase):
    """Content detail."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='id')
    view_count: int = Field(description='view count')
    sort_order: int = Field(description='sort order')
    created_by: int = Field(description='created by')
    updated_by: int | None = Field(None, description='updated by')
    created_time: datetime = Field(description='created time')
    updated_time: datetime | None = Field(None, description='updated time')


class GetContentListDetail(SchemaBase):
    """Content list item."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='id')
    title: str = Field(description='title')
    slug: str = Field(description='slug')
    summary: str | None = Field(None, description='summary')
    cover_image: str | None = Field(None, description='cover image url')
    category_id: int | None = Field(None, description='category id')
    tags: list[str] | None = Field(None, description='tags')
    is_pinned: bool = Field(description='is pinned')
    is_public: bool = Field(description='is public')
    is_published: bool = Field(description='is published')
    publish_time: datetime | None = Field(None, description='publish time')
    view_count: int = Field(description='view count')
    created_by: int = Field(description='created by')
    created_time: datetime = Field(description='created time')
