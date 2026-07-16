#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SpaceType(str, Enum):
    """文件空间类型。"""

    PERSONAL = 'personal'
    SHARE_LINK = 'share_link'
    GROUP = 'group'
    FRIEND = 'friend'
    OPENLIST = 'openlist'


@dataclass(frozen=True, slots=True)
class SpaceLocator:
    """文件空间定位信息。"""

    provider: str
    space_type: SpaceType
    account_id: str | None = None
    source_id: str | None = None
    root_id: str | None = None
    root_path: str = '/'
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        """获取稳定的文件空间标识。"""
        account_part = self.account_id or '-'
        source_part = self.source_id or '-'
        return f'{self.provider}:{self.space_type.value}:{account_part}:{source_part}:{self.root_id or self.root_path}'


@dataclass(frozen=True, slots=True)
class FileObject:
    """统一文件对象。"""

    space: SpaceLocator
    file_id: str
    name: str
    path: str
    is_directory: bool = False
    size: int | None = None
    parent_id: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    hash_value: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ShareLink:
    """文件分享链接。"""

    provider: str
    share_id: str
    title: str
    url: str
    password: str = ''
    expires_in_days: int = 0
    expired_at: datetime | None = None
