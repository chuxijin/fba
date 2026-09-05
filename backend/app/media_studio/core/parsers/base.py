#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
from abc import ABC, abstractmethod

import httpx

from backend.app.media_studio.schema.media import UnifiedMediaResponse
from backend.common.exception import errors


class BaseMediaParser(ABC):
    """媒体解析器抽象基类"""

    PLATFORM: str = ""
    DEFAULT_TIMEOUT: float = 15.0

    @staticmethod
    def extract_url(text: str) -> str:
        """从字符串中提取第一个合法的 HTTP(S) 链接"""
        pattern = r"https?://[a-zA-Z0-9][-a-zA-Z0-9.]*(?::[0-9]+)?(?:/[^\s<>'\"`()]*)*"
        match = re.search(pattern, text)
        if not match:
            raise errors.RequestError(msg="未在输入文本中找到有效的分享链接")
        return match.group(0).strip()

    async def get_redirected_url(self, url: str, headers: dict[str, str] | None = None) -> str:
        """追踪获取 302/301 重定向后的最终落地 URL"""
        default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
            )
        }
        if headers:
            default_headers.update(headers)

        async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT, follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=default_headers)
                return str(response.url)
            except Exception as e:
                raise errors.RequestError(msg=f"解析链接重定向失败: {e}")

    @abstractmethod
    async def parse(self, raw_input: str, cookie: str | None = None) -> UnifiedMediaResponse:
        """解析作品内容并返回统一规范的结构化数据"""
        pass