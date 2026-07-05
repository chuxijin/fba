#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenList 数据结构定义"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class OpenListFile:
    """OpenList 文件信息"""

    name: str
    path: str
    size: int
    is_dir: bool
    modified: str
    created: str
    sign: str = ''
    thumb: str = ''
    type: int = 0
    hashinfo: str = 'null'
    hash_info: Optional[Dict[str, Any]] = None


@dataclass
class OpenListQuota:
    """OpenList 配额信息"""

    quota: int
    used: int


@dataclass
class OpenListResponse:
    """OpenList API 响应"""

    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


@dataclass
class OpenListListResponse:
    """OpenList 文件列表响应"""

    content: List[OpenListFile]
    total: int
    readme: str = ''
    header: str = ''
    write: bool = True
    provider: str = 'unknown'


@dataclass
class OpenListOperationResponse:
    """OpenList 操作响应"""

    success: bool
    message: str = ''
    task_id: Optional[str] = None
