#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import UploadFile


@dataclass
class ProviderUploadContext:
    """上传上下文"""

    file: UploadFile
    object_key: str
    use_signed_url: bool
    signed_url_expire_seconds: int
    object_expire_days: int | None


class StorageProvider(Protocol):
    """存储 provider 协议"""

    async def upload(self, context: ProviderUploadContext) -> str:
        """
        Upload file and return url.

        :param context: upload context
        :return:
        """
        ...

    async def delete(self, object_key: str) -> bool:
        """
        Delete object by key. Return True if deleted or not existed.

        :param object_key: object key
        :return:
        """
        ...
