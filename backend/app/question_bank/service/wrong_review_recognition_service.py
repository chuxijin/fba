#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import binascii
import html
import json
import re

from typing import TYPE_CHECKING, Any

from backend.app.question_bank.schema.wrong_review import (
    RecognizeCustomQuestionResult,
    RecognizedQuestionOption,
)
from backend.common.exception import errors
from backend.core.conf import settings
from backend.plugin.ai.schema.chat import AIChat, AIChatMessage
from backend.plugin.ai.service.chat_service import ai_chat_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

VISION_PROMPT = """你是错题图片结构化识别助手。请阅读所有题目截图，识别一题选择题并只返回 JSON 对象。

返回格式：
{
  "stem": "题干文本",
  "options": [{"option_code": "A", "content": "选项文本"}],
  "answer": "", "explanation": "解析文本"
}

规则：
- 只识别截图中明确存在的内容，无法确认答案或解析时返回空字符串。
- 必须保留题面原有的逻辑分段和换行：题干的不同条件、材料段、设问分别换行；
  解析的每个步骤、每个结论分别换行。不要将多段内容合并成一整段文字。
- 正文允许使用 **加粗内容** 标记题面中明确加粗、强调或小标题的文字；不得输出其他 Markdown 或 HTML。
- 简单公式、等式、分式、根式或上下标使用标准 LaTeX，行内公式写为 $...$，独立公式写为 $$...$$。
- LaTeX 只使用 KaTeX 支持的基础命令，例如 \\frac、\\sqrt、^、_、\\times、\\div、\\le、\\ge、\\neq、\\sum、\\int。
- 复杂公式、手写公式、长推导或无法可靠转写的公式不要臆测转写；
  在对应文字中标注“请保留原图公式”，由用户在确认页手动裁剪添加。
- 如题面存在 A、B、C、D 等选择项，options 必须完整返回每个选项，即使选项内容只有一个字母、数字、
  符号或公式；编码只能为 A-F，按题面顺序排列。不要把选项混入 stem。
- 只输出题目原文、选项原文、答案和题面明确给出的解析；不要生成图像描述、图片说明、图表概述、
  “图中显示”等补充文字，也不要将图片内容改写成自然语言描述。
- 不要返回图片坐标、regions、图片链接、HTML 或图片占位符；用户会在确认页自行裁剪原图。
- 不要在 stem 或 content 中输出 HTML 或 Markdown（允许规则中定义的 **加粗** 与 LaTeX）。"""


class WrongReviewRecognitionService:
    """错题图片识别服务"""

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        """
        解析 AI JSON 响应

        :param content: AI 响应文本
        :return:
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]*\}', content)
            if not match:
                raise errors.GatewayError(msg='视觉模型未返回有效的结构化结果')
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError as exc:
                raise errors.GatewayError(msg='视觉模型返回的结构化结果格式错误') from exc

        if not isinstance(data, dict):
            raise errors.GatewayError(msg='视觉模型返回的结构化结果格式错误')
        return data

    @staticmethod
    def _text_to_html(value: object) -> str:
        """
        将识别文本转为安全富文本

        :param value: 识别文本
        :return:
        """
        text = str(value or '').strip()
        if not text:
            return ''
        escaped_text = html.escape(text)
        formatted_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escaped_text)
        return formatted_text.replace('\n', '<br/>')

    @staticmethod
    def _normalize_options(value: object) -> list[dict[str, str]]:
        """
        规范化识别选项

        :param value: AI 返回的选项
        :return:
        """
        if isinstance(value, dict):
            value = [
                {'option_code': code, 'content': content}
                for code, content in value.items()
            ]
        if not isinstance(value, list):
            return []

        options: list[dict[str, str]] = []
        used_codes: set[str] = set()
        for item in value:
            if isinstance(item, str):
                match = re.match(r'^\s*([A-F])[.、:：)）\s]*(.*)$', item, re.IGNORECASE | re.DOTALL)
                if not match:
                    continue
                item = {'option_code': match.group(1), 'content': match.group(2)}
            if not isinstance(item, dict):
                continue
            code = str(item.get('option_code') or '').strip().upper()
            if code not in {'A', 'B', 'C', 'D', 'E', 'F'} or code in used_codes:
                continue
            used_codes.add(code)
            options.append(
                {
                    'option_code': code,
                    'content': WrongReviewRecognitionService._text_to_html(item.get('content')),
                }
            )
        return options

    @staticmethod
    def _decode_images(images: list[str]) -> list[bytes]:
        """
        解码本地图片数据

        :param images: Base64 Data URL 数组
        :return:
        """
        max_bytes = int(settings.WRONG_REVIEW_VISION_MAX_IMAGE_BYTES)
        decoded_images: list[bytes] = []
        for image_data in images:
            if not image_data.startswith('data:image/') or ';base64,' not in image_data:
                raise errors.RequestError(msg='识别图片格式无效')
            encoded_data = image_data.split(';base64,', maxsplit=1)[1]
            try:
                content = base64.b64decode(encoded_data, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise errors.RequestError(msg='识别图片数据无效') from exc
            if not content or len(content) > max_bytes:
                raise errors.RequestError(msg='题目图片为空或超过识别大小限制')
            decoded_images.append(content)
        return decoded_images

    @staticmethod
    async def recognize(
        *, db: AsyncSession, images: list[str]
    ) -> RecognizeCustomQuestionResult:
        """
        识别题目图片并生成可编辑草稿

        :param db: 数据库会话
        :param images: 本地图片 Base64 Data URL 数组
        :return:
        """
        image_bytes = WrongReviewRecognitionService._decode_images(images)
        content_parts: list[dict[str, Any]] = [{'type': 'text', 'text': VISION_PROMPT}]
        for index, content in enumerate(image_bytes):
            encoded = base64.b64encode(content).decode('ascii')
            content_parts.extend([
                {'type': 'text', 'text': f'第 {index + 1} 张原图，source_image_index={index}。'},
                {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{encoded}'}},
            ])

        chat = AIChat(
            provider_id=settings.WRONG_REVIEW_VISION_PROVIDER_ID,
            model_id=settings.WRONG_REVIEW_VISION_MODEL_ID,
            messages=[AIChatMessage(role='user', content=content_parts)],
            temperature=0.05,
            max_tokens=4096,
            extra_body={'response_format': {'type': 'json_object'}},
        )
        response = await ai_chat_service.raw_chat(db=db, chat=chat, stream=True)
        result = WrongReviewRecognitionService._parse_json(str(response.get('content') or ''))
        options = WrongReviewRecognitionService._normalize_options(result.get('options'))
        stem = WrongReviewRecognitionService._text_to_html(result.get('stem'))
        explanation = WrongReviewRecognitionService._text_to_html(result.get('explanation'))
        warnings: list[str] = []
        if not stem:
            warnings.append('未识别到题干文字，请在确认页补充。')
        if not options:
            warnings.append('未识别到有效选项，请在确认页补充。')

        return RecognizeCustomQuestionResult(
            images=[],
            stem=stem,
            options=[RecognizedQuestionOption(**item) for item in options],
            answer=str(result.get('answer') or '').strip(),
        explanation=explanation,
            assets=[],
            warnings=list(dict.fromkeys(warnings)),
        )


wrong_review_recognition_service: WrongReviewRecognitionService = WrongReviewRecognitionService()
