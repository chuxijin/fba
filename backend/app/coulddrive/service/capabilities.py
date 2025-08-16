#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网盘客户端能力协议定义
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Any

from backend.app.coulddrive.schema.file import (
    BaseFileInfo,
    BaseShareInfo,
    CancelShareParam,
    ListFilesParam,
    ListShareFilesParam,
    ListShareInfoParam,
    MkdirParam,
    RemoveParam,
    ShareParam,
    TransferParam,
    UserInfoParam,
)
from backend.app.coulddrive.schema.user import BaseUserInfo, RelationshipItem


@runtime_checkable
class DriveCapabilities(Protocol):
    """约束各网盘客户端的统一能力签名"""

    async def get_user_info(self, params: UserInfoParam, **kwargs: Any) -> BaseUserInfo: ...

    async def get_quota(self, params: ListFilesParam, **kwargs: Any) -> dict[str, Any]: ...

    async def get_relationship_list(self, params: RemoveParam, **kwargs: Any) -> list[RelationshipItem]: ...

    async def mkdir(self, params: MkdirParam, **kwargs: Any) -> BaseFileInfo: ...

    async def remove(self, params: RemoveParam, **kwargs: Any) -> bool: ...

    async def get_disk_list(self, params: ListFilesParam, **kwargs: Any) -> list[BaseFileInfo]: ...

    async def get_share_list(self, params: ListShareFilesParam, **kwargs: Any) -> list[BaseFileInfo]: ...

    async def get_share_info(self, params: ListShareInfoParam, **kwargs: Any) -> list[BaseShareInfo]: ...

    async def create_share(self, params: ShareParam, **kwargs: Any) -> BaseShareInfo: ...

    async def cancel_share(self, params: CancelShareParam, **kwargs: Any) -> bool: ...

    async def transfer(self, params: TransferParam, **kwargs: Any) -> bool: ...


