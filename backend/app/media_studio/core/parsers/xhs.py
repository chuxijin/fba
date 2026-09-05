#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
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


class XHSParser(BaseMediaParser):
    """小红书平台作品解析器（基于 SSR 原生状态解析，免接口签名逆向，支持图文与视频高清去水印）"""

    PLATFORM: str = "xhs"

    async def parse(self, raw_input: str, cookie: str | None = None) -> UnifiedMediaResponse:
        url = self.extract_url(raw_input)
        log.info(f"[XHSParser] 开始解析链接: {url}")

        final_url = await self.get_redirected_url(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                )
            },
        )
        log.info(f"[XHSParser] 最终落地链接: {final_url}")

        note_id = self._extract_note_id(final_url)
        if not note_id:
            raise errors.RequestError(msg=f"未能从小红书链接中提取到笔记 ID: {final_url}")

        html = await self._fetch_note_html(final_url, cookie=cookie)
        note_data = self._extract_note_data_from_html(html, note_id=note_id)
        return self._format_response(note_data, raw_url=final_url)

    def _extract_note_id(self, url: str) -> str | None:
        """提取小红书笔记 ID"""
        patterns = [
            r"/(?:explore|discovery/item)/([a-zA-Z0-9]+)",
            r"noteId=([a-zA-Z0-9]+)",
        ]
        for p in patterns:
            match = re.search(p, url)
            if match:
                return match.group(1)
        return None

    async def _fetch_note_html(self, url: str, cookie: str | None = None) -> str:
        """获取笔记页面 HTML"""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.xiaohongshu.com/",
        }
        if cookie:
            headers["Cookie"] = cookie

        async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT, follow_redirects=True) as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return resp.text
            except Exception as e:
                log.error(f"[XHSParser] 抓取小红书页面失败: {e}")
                raise errors.RequestError(msg=f"抓取小红书页面失败: {e}")

        raise errors.RequestError(msg="访问小红书页面受限，可能遇到风控或链接已失效")

    def _extract_note_data_from_html(self, html: str, note_id: str) -> dict[str, Any]:
        """从 HTML 源码中正则提取 window.__INITIAL_STATE__"""
        patterns = [
            r"<script>window\.__INITIAL_STATE__\s*=\s*(\{.+?\})</script>",
            r"<script>window\.__INITIAL_SSR_STATE__\s*=\s*(\{.+?\})</script>",
        ]
        json_str: str | None = None
        for p in patterns:
            match = re.search(p, html, re.DOTALL)
            if match:
                json_str = match.group(1)
                break

        if not json_str:
            raise errors.RequestError(msg="解析小红书页面失败：未找到初始渲染状态数据，可能被平台重定向至验证码页")

        # 替换 JS 中的 undefined 为 null 以便合法转为 JSON
        cleaned_json = re.sub(r":\s*undefined", ": null", json_str)
        try:
            state_data = json.loads(cleaned_json)
        except Exception as e:
            log.error(f"[XHSParser] 解析初始状态 JSON 失败: {e}")
            raise errors.RequestError(msg="小红书数据反序列化失败")

        note_detail_map = state_data.get("note", {}).get("noteDetailMap", {})
        if note_id in note_detail_map:
            return note_detail_map[note_id].get("note") or {}

        # 尝试匹配第一条记录
        if note_detail_map:
            first_item = next(iter(note_detail_map.values()))
            if isinstance(first_item, dict) and "note" in first_item:
                return first_item["note"]

        raise errors.RequestError(msg="未能在小红书页面数据中找到对应笔记详情，可能需登录或配置 Cookie")

    def _clean_image_url(self, raw_img_url: str) -> str:
        """格式化小红书图片 URL，保留完整的签名防篡改校验，并升级为 HTTPS 协议"""
        if not raw_img_url:
            return ""
        url = raw_img_url.strip()
        if url.startswith("http://"):
            url = "https://" + url[7:]
        # 注意：小红书新版 CDN 图片签名 Hash 绑定了样式后缀，不可用 split('!') 截断，否则报 403
        return url

    def _format_response(self, note: dict[str, Any], raw_url: str) -> UnifiedMediaResponse:
        """格式化小红书数据"""
        title = note.get("title", "").strip()
        desc = note.get("desc", "").strip()
        note_type = note.get("type", "normal")  # normal(图文) / video(视频)

        # 标签
        tags: list[str] = []
        for tag in note.get("tagList", []):
            name = tag.get("name")
            if name and name not in tags:
                tags.append(name)
        if not tags and "#" in desc:
            tags = re.findall(r"#([\w\u4e00-\u9fa5]+)", desc)

        # 图片列表处理
        raw_images = note.get("imageList") or []
        images: list[str] = []
        for img_item in raw_images:
            img_url = (
                img_item.get("urlDefault")
                or (img_item.get("infoList", [{}])[0].get("url") if img_item.get("infoList") else None)
            )
            if img_url:
                images.append(self._clean_image_url(img_url))

        cover_url = images[0] if images else None
        video_url: str | None = None
        media_type = "image"

        if note_type == "video":
            media_type = "video"
            video_info = note.get("video") or {}
            media_info = video_info.get("media") or {}
            stream_info = media_info.get("stream") or {}
            h264_list = stream_info.get("h264") or []
            if h264_list:
                video_url = h264_list[0].get("masterUrl")
            elif stream_info.get("h265"):
                video_url = stream_info["h265"][0].get("masterUrl")

        # 作者
        user = note.get("user") or {}
        author = MediaAuthor(
            id=str(user.get("userId") or ""),
            name=user.get("nickname") or "未知作者",
            avatar=user.get("avatar"),
            url=f"https://www.xiaohongshu.com/user/profile/{user.get('userId')}" if user.get("userId") else None,
        )

        # 互动数据
        interact = note.get("interactInfo") or {}
        stats = MediaStats(
            like_count=interact.get("likedCount"),
            comment_count=interact.get("commentCount"),
            collect_count=interact.get("collectedCount"),
            share_count=interact.get("shareCount"),
        )

        return UnifiedMediaResponse(
            platform=self.PLATFORM,
            media_type=media_type,
            title=title or (desc[:30] if desc else "小红书笔记"),
            content=desc,
            tags=tags,
            cover_url=cover_url,
            images=images,
            video_url=video_url,
            author=author,
            stats=stats,
            raw_url=raw_url,
        )