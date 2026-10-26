#!/usr/bin/env python3
from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, field_serializer, field_validator, model_validator

from backend.common.schema import SchemaBase

ShareScene = Literal['default', 'home', 'invite', 'resource', 'group_buy', 'ability']
SHARE_SCENES = ('default', 'home', 'invite', 'resource', 'group_buy', 'ability')
SHARE_VARIABLES = {
    'default': {'brand'},
    'home': {'brand'},
    'invite': {'brand'},
    'resource': {'brand', 'resource_title'},
    'group_buy': {'brand', 'product_name', 'people'},
    'ability': {'brand'},
}


def validate_image_url(value: str | None) -> str | None:
    """分享素材使用可公开访问的 HTTPS PNG/JPG；允许无后缀的图片服务地址。"""
    if not value or not value.strip():
        return None
    value = value.strip()
    url = urlsplit(value)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError('分享图片必须使用公开可访问的 HTTPS 地址')
    suffix = PurePosixPath(url.path).suffix.lower()
    if suffix and suffix not in {'.png', '.jpg', '.jpeg'}:
        raise ValueError('微信分享图片仅支持 PNG/JPG')
    return value


class ShareSettings(SchemaBase):
    """存储在 CmsSlot.extra.share；模板生成使用客户端内置 brand-v1。"""

    model_config = ConfigDict(extra='forbid')

    cover_mode: Literal['static', 'template'] = 'static'
    timeline_image_url: str | None = Field(None, max_length=500)
    poster_mode: Literal['disabled', 'static', 'template'] = 'disabled'
    poster_image_url: str | None = Field(None, max_length=500)

    _image_urls = field_validator('timeline_image_url', 'poster_image_url')(validate_image_url)

    @model_validator(mode='after')
    def validate_poster(self) -> 'ShareSettings':
        if self.poster_mode == 'static' and not self.poster_image_url:
            raise ValueError('静态海报需要上传海报图片')
        return self


class ShareMaterial(SchemaBase):
    scene: ShareScene
    code: str
    title: str | None = None
    description: str | None = None
    image_url: str | None = None
    settings: ShareSettings = Field(default_factory=ShareSettings)
    valid_until: datetime | None = None

    @field_serializer('valid_until')
    def serialize_valid_until(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None


class ShareCatalog(SchemaBase):
    materials: list[ShareMaterial]
    cache_seconds: int = 60
    server_time: datetime

    @field_serializer('server_time')
    def serialize_server_time(self, value: datetime) -> str:
        # 避免全局展示日期格式丢失时区，iOS/跨时区客户端按同一时刻判断素材有效期。
        return value.isoformat()
