from pydantic import Field

from backend.common.schema import SchemaBase


class HaloPostItem(SchemaBase):
    """文章列表项"""

    name: str = Field(..., description='Halo 内部标识')
    title: str = Field(..., description='标题')
    slug: str = Field(..., description='别名')
    excerpt: str = Field('', description='摘要')
    cover: str = Field('', description='封面图')
    publish_time: str | None = Field(None, description='发布时间')
    categories: list[str] = Field(default_factory=list, description='分类名称列表')
    tags: list[str] = Field(default_factory=list, description='标签名称列表')
    view_count: int = Field(0, description='浏览量')


class HaloPostDetail(HaloPostItem):
    """文章详情"""

    content: str = Field('', description='HTML 内容')


class HaloCategoryItem(SchemaBase):
    """分类"""

    name: str = Field(..., description='Halo 内部标识')
    display_name: str = Field(..., description='显示名称')
    slug: str = Field(..., description='别名')
    post_count: int = Field(0, description='文章数量')


class HaloTagItem(SchemaBase):
    """标签"""

    name: str = Field(..., description='Halo 内部标识')
    display_name: str = Field(..., description='显示名称')
    slug: str = Field(..., description='别名')
