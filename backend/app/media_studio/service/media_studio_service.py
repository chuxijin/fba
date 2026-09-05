#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.media_studio.core.parsers import DouyinParser, XHSParser
from backend.app.media_studio.core.parsers.base import BaseMediaParser
from backend.app.media_studio.schema.media import (
    MediaParseParam,
    OneClickRecreateParam,
    OneClickRecreateResult,
    UnifiedMediaResponse,
)
from backend.common.exception import errors
from backend.plugin.ai.schema.image import (
    AIImageGenerateParam,
    AIImageGenerateResult,
)
from backend.plugin.ai.service.image_service import image_service


class MediaStudioService:
    """媒体工作室业务服务：聚合平台解析、AI中转站容灾生图、一键二创流程"""

    def __init__(self) -> None:
        self.douyin_parser = DouyinParser()
        self.xhs_parser = XHSParser()

    async def parse_media(self, params: MediaParseParam) -> UnifiedMediaResponse:
        """
        统一解析平台作品（自动识别抖音、小红书）

        :param params: 解析入参
        :return: 统一格式作品数据
        """
        url = BaseMediaParser.extract_url(params.url_or_text)

        if "douyin.com" in url or "iesdouyin.com" in url:
            return await self.douyin_parser.parse(params.url_or_text, cookie=params.cookie)

        if "xiaohongshu.com" in url or "xhslink.com" in url:
            return await self.xhs_parser.parse(params.url_or_text, cookie=params.cookie)

        raise errors.RequestError(
            msg="暂不支持该平台链接，当前支持：抖音 (v.douyin.com / douyin.com) 和 小红书 (xhslink.com / xiaohongshu.com)"
        )

    async def generate_image(
        self,
        *,
        db: AsyncSession,
        param: AIImageGenerateParam,
    ) -> AIImageGenerateResult:
        """
        单步生图服务（复用 plugin/ai 模块，带多中转站故障转移）

        :param db: 数据库会话
        :param param: 生图参数
        :return:
        """
        return await image_service.generate(db=db, param=param)

    async def one_click_recreate(
        self,
        *,
        db: AsyncSession,
        param: OneClickRecreateParam,
    ) -> OneClickRecreateResult:
        """
        一键二创全自动流程：解析作品 -> 智能提炼视觉生图 Prompt -> 调用中转站容灾生图

        :param db: 数据库会话
        :param param: 一键二创入参
        :return: 包含原作品与新生成二创图片的完整结果
        """
        start_time = time.perf_counter()

        # 1. 解析原作品
        media_data = await self.parse_media(
            MediaParseParam(url_or_text=param.url_or_text, cookie=getattr(param, 'cookie', None))
        )

        # 2. 针对教育学习笔记构建专属高转化内容图二创 Prompt
        title = (media_data.title or "").strip()
        desc = (media_data.content or "").strip()
        subject_theme = title if title else desc[:80]
        if not subject_theme:
            subject_theme = "备考干货与知识点梳理"

        prompt_parts: list[str] = [
            f"小红书教育学习笔记正文内容图二创，围绕主题「{subject_theme}」。"
        ]

        if param.reference_image_url:
            prompt_parts.append("严格参考指定参考图的版式结构、信息层级和构图比例进行同构二创。")

        if param.custom_prompt and param.custom_prompt.strip():
            prompt_parts.append(f"核心指令与要求：{param.custom_prompt.strip()}。")

        if param.prompt_style and param.prompt_style.strip():
            prompt_parts.append(f"画面风格：{param.prompt_style.strip()}。")

        prompt_parts.append(
            "构图规范：教育笔记正文排版，结构严谨分明，色彩整洁护眼，无低质乱码字符，具备专业教研讲义质感，8k超清。"
        )

        prompt = " ".join(prompt_parts)

        # 3. 调度多中转站生图服务（传入参考图）
        gen_param = AIImageGenerateParam(
            prompt=prompt,
            model=param.model,
            size=param.size,
            n=1,
            image_url=param.reference_image_url,
            provider_id=param.provider_id,
        )
        gen_result = await image_service.generate(db=db, param=gen_param)

        elapsed = round(time.perf_counter() - start_time, 2)

        return OneClickRecreateResult(
            original_media=media_data,
            generated_prompt=prompt,
            generated_images=[img.url for img in gen_result.images],
            provider_name=gen_result.provider_name,
            elapsed_seconds=elapsed,
        )


media_studio_service: MediaStudioService = MediaStudioService()