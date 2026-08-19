#!/usr/bin/env python3
import json
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_practice_log import practice_log_dao
from backend.app.gongkao.schema.practice_log_vision import (
    ImportPracticeLogVisionParam,
    ImportPracticeLogVisionResult,
)
from backend.common.exception import errors
from backend.plugin.ai.model import AIProvider, AIModel
from backend.plugin.ai.schema.chat import AIChat, AIChatMessage
from backend.plugin.ai.service.chat_service import ai_chat_service

DEFAULT_PROMPT = """你是一个练习记录解析助手。请从这张练习/模考截图里提取数据，返回 JSON，格式如下：
{
  "material_type": "exam" | "practice" | "special",
  "material_title": "完整标题",
  "total_questions": 130,
  "correct_count": 96,
  "duration_raw": "104分19秒",
  "duration_seconds": 6259,
  "modules": [
    {
      "module_name": "言语理解与表达",
      "total_questions": 30,
      "correct_count": 21,
      "duration_raw": "15分09秒",
      "duration_seconds": 909,
      "seq_no": 1
    }
  ]
}

要求：
- material_type: exam=模考/考试, practice=日常练习, special=专项练习，根据标题判断
- duration_raw: 截图中显示的原始时间文字，原样复制，如 "104分19秒" "1小时45分" "90秒"
- duration_seconds: 换算为秒，如"104分19秒"→6259
- modules 按模块出现的顺序排列 seq_no，没有模块明细就传空数组
- 只返回 JSON，不要加任何说明文字"""


class PracticeLogVisionService:
    """练习记录 AI 智能导入服务"""

    @staticmethod
    async def import_from_vision(
        *, db: AsyncSession, user_id: int, obj: ImportPracticeLogVisionParam
    ) -> ImportPracticeLogVisionResult:
        provider_id = obj.provider_id
        model_id = obj.model_id

        # 未指定供应商/模型时，取第一个启用的供应商下的第一个启用模型
        if not provider_id or not model_id:
            stmt = select(AIProvider).where(AIProvider.status == 1).order_by(AIProvider.id.asc()).limit(1)
            result = await db.execute(stmt)
            provider = result.scalar_one_or_none()
            if not provider:
                raise errors.NotFoundError(msg='未找到可用的 AI 供应商，请先在 AI 设置中配置')
            provider_id = provider.id
            if not model_id:
                stmt = select(AIModel).where(
                    AIModel.provider_id == provider_id, AIModel.status == 1
                ).order_by(AIModel.id.asc()).limit(1)
                result = await db.execute(stmt)
                model = result.scalar_one_or_none()
                if not model:
                    raise errors.NotFoundError(msg=f'供应商"{provider.name}"下没有可用的模型')
                model_id = model.model_id

        prompt = obj.prompt or DEFAULT_PROMPT

        image_url = f'data:image/jpeg;base64,{obj.image_base64}'

        chat = AIChat(
            provider_id=provider_id,
            model_id=model_id,
            messages=[
                AIChatMessage(role='user', content=[
                    {'type': 'text', 'text': prompt},
                    {'type': 'image_url', 'image_url': {'url': image_url}},
                ]),
            ],
            temperature=0.1,
            max_tokens=4096,
        )

        result = await ai_chat_service.raw_chat(db=db, chat=chat)
        content = result.get('content', '')

        # 尝试提取 JSON
        data = PracticeLogVisionService._parse_json(content)

        if not data:
            raise errors.ServerError(msg='AI 未能正确解析图片内容，请重试或换一张图片')

        PracticeLogVisionService._normalize_duration(data)

        return ImportPracticeLogVisionResult(
            material_type=data.get('material_type', 'exam'),
            material_title=data.get('material_title', ''),
            total_questions=data.get('total_questions', 0),
            correct_count=data.get('correct_count', 0),
            duration_seconds=data.get('duration_seconds'),
            modules=data.get('modules', []),
            raw_raw=content,
        )

    @staticmethod
    def _parse_duration_text(text: str) -> int | None:
        """从原始时间文本中解析秒数，如 '104分19秒' → 6259"""
        if not text:
            return None

        text = str(text).strip()
        if not text:
            return None

        hours = 0
        minutes = 0
        seconds = 0
        found = False

        h_match = re.search(r'(\d+)\s*小?时', text)
        if h_match:
            hours = int(h_match.group(1))
            found = True

        m_match = re.search(r'(\d+)\s*分', text)
        if m_match:
            minutes = int(m_match.group(1))
            found = True

        s_match = re.search(r'(\d+)\s*秒', text)
        if s_match:
            seconds = int(s_match.group(1))
            found = True

        if found:
            return hours * 3600 + minutes * 60 + seconds

        # 纯数字时尝试作为秒数
        if text.isdigit():
            return int(text)

        return None

    @staticmethod
    def _normalize_duration(data: dict) -> None:
        """用 duration_raw 原始文本重新解析秒数，覆盖 AI 可能算错的 duration_seconds"""
        raw = data.get('duration_raw')
        if raw:
            parsed = PracticeLogVisionService._parse_duration_text(raw)
            if parsed is not None:
                data['duration_seconds'] = parsed

        for module in data.get('modules', []) or []:
            m_raw = module.get('duration_raw')
            if m_raw:
                m_parsed = PracticeLogVisionService._parse_duration_text(m_raw)
                if m_parsed is not None:
                    module['duration_seconds'] = m_parsed

    @staticmethod
    def _parse_json(content: str) -> dict | None:
        """从 AI 返回内容中提取 JSON"""
        if not content:
            return None

        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 代码块
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取最外层 { }
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None


practice_log_vision_service: PracticeLogVisionService = PracticeLogVisionService()
