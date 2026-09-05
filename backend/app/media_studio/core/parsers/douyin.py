#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
from typing import Any

import httpx

from backend.app.media_studio.core.parsers.base import BaseMediaParser
from backend.app.media_studio.schema.media import (
    MediaAuthor,
    MediaStats,
    UnifiedMediaResponse,
)
from backend.common.exception import errors
from backend.common.log import log


class DouyinParser(BaseMediaParser):
    """抖音平台作品解析器（免无头浏览器、纯异步、支持图文与视频去水印）"""

    PLATFORM: str = "douyin"

    DETAIL_API_URL: str = (
        "https://www.iesdouyin.com/aweme/v1/web/aweme/detail/?aweme_id={aweme_id}&aid=1128&version_code=190500&channel=channel_pc_web"
    )
    FALLBACK_API_URL: str = (
        "https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={aweme_id}&device_platform=webapp&aid=6383"
    )

    async def parse(self, raw_input: str, cookie: str | None = None) -> UnifiedMediaResponse:
        url = self.extract_url(raw_input)
        log.info(f"[DouyinParser] 开始解析链接: {url}")

        final_url = await self.get_redirected_url(url)
        log.info(f"[DouyinParser] 最终落地链接: {final_url}")

        aweme_id = self._extract_aweme_id(final_url)
        if not aweme_id:
            raise errors.RequestError(msg=f"未能从落地链接中提取到抖音作品 ID: {final_url}")

        detail_data = await self._fetch_aweme_detail(aweme_id, cookie=cookie)
        return self._format_response(detail_data, raw_url=final_url)

    def _extract_aweme_id(self, url: str) -> str | None:
        """从重定向后的 URL 中提取 aweme_id"""
        patterns = [
            r"/(?:video|note)/(\d+)",
            r"modal_id=(\d+)",
            r"aweme_id=(\d+)",
        ]
        for p in patterns:
            match = re.search(p, url)
            if match:
                return match.group(1)
        return None

    async def _fetch_aweme_detail(self, aweme_id: str, cookie: str | None = None) -> dict[str, Any]:
        """请求抖音详情接口"""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
            ),
            "Referer": "https://www.douyin.com/",
            "Accept": "application/json",
        }
        if cookie:
            headers["Cookie"] = cookie

        async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT) as client:
            # 1. 尝试主接口
            api_url = self.DETAIL_API_URL.format(aweme_id=aweme_id)
            try:
                resp = await client.get(api_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("aweme_detail"):
                        return data["aweme_detail"]
            except Exception as e:
                log.warning(f"[DouyinParser] 主接口请求失败: {e}，尝试备用接口")

            # 2. 尝试备用接口
            fallback_url = self.FALLBACK_API_URL.format(aweme_id=aweme_id)
            try:
                resp = await client.get(fallback_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("aweme_detail"):
                        return data["aweme_detail"]
            except Exception as e:
                log.error(f"[DouyinParser] 备用接口请求失败: {e}")

        raise errors.RequestError(msg="获取抖音作品详情失败，该作品可能已删除、私密或触发了平台风控")

    def _format_response(self, detail: dict[str, Any], raw_url: str) -> UnifiedMediaResponse:
        """格式化为统一作品数据结构"""
        desc = detail.get("desc", "").strip()

        # 提取话题标签
        tags: list[str] = []
        for text_extra in detail.get("text_extra", []):
            tag_name = text_extra.get("hashtag_name")
            if tag_name and tag_name not in tags:
                tags.append(tag_name)
        if not tags and "#" in desc:
            tags = re.findall(r"#([\w\u4e00-\u9fa5]+)", desc)

        # 判断图文 or 视频
        images_list = detail.get("images") or []
        aweme_type = detail.get("aweme_type")
        is_image = bool(images_list) or aweme_type == 68

        images: list[str] = []
        video_url: str | None = None
        cover_url: str | None = None

        if is_image:
            media_type = "image"
            for img in images_list:
                url_list = img.get("url_list") or []
                if url_list:
                    images.append(url_list[0])
            if images:
                cover_url = images[0]
        else:
            media_type = "video"
            video_info = detail.get("video") or {}
            # 封面图
            cover_urls = video_info.get("cover", {}).get("url_list") or []
            if cover_urls:
                cover_url = cover_urls[0]

            # 无水印视频提取：替换 playwm 为 play
            play_addr_list = video_info.get("play_addr", {}).get("url_list") or []
            if play_addr_list:
                raw_video_url = play_addr_list[0]
                video_url = raw_video_url.replace("playwm", "play")

        # 作者信息
        author_data = detail.get("author") or {}
        author_avatar_list = author_data.get("avatar_thumb", {}).get("url_list") or []
        author = MediaAuthor(
            id=str(author_data.get("sec_uid") or author_data.get("uid") or ""),
            name=author_data.get("nickname") or "未知作者",
            avatar=author_avatar_list[0] if author_avatar_list else None,
            url=f"https://www.douyin.com/user/{author_data.get('sec_uid')}" if author_data.get("sec_uid") else None,
        )

        # 互动数据
        stats_data = detail.get("statistics") or {}
        stats = MediaStats(
            like_count=stats_data.get("digg_count"),
            comment_count=stats_data.get("comment_count"),
            collect_count=stats_data.get("collect_count"),
            share_count=stats_data.get("share_count"),
        )

        return UnifiedMediaResponse(
            platform=self.PLATFORM,
            media_type=media_type,
            title=desc[:50] if desc else "抖音作品",
            content=desc,
            tags=tags,
            cover_url=cover_url,
            images=images,
            video_url=video_url,
            author=author,
            stats=stats,
            raw_url=raw_url,
        )