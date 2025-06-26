#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alist 数据结构定义
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class AlistFile:
    """Alist 文件信息"""
    name: str
    path: str
    size: int
    is_dir: bool
    modified: str
    created: str
    sign: str = ""
    thumb: str = ""
    type: int = 0
    hashinfo: str = "null"
    hash_info: Optional[Dict[str, Any]] = None


@dataclass
class AlistQuota:
    """Alist 配额信息"""
    quota: int
    used: int


@dataclass
class AlistResponse:
    """Alist API 响应"""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


@dataclass
class AlistListResponse:
    """Alist 文件列表响应"""
    content: List[AlistFile]
    total: int
    readme: str = ""
    header: str = ""
    write: bool = True
    provider: str = "unknown"


@dataclass
class AlistOperationResponse:
    """Alist 操作响应"""
    success: bool
    message: str = ""
    task_id: Optional[str] = None
