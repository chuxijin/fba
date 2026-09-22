# -*- coding: utf-8 -*-
"""
通用题本数据适配器
用于非公考真题类的通用题本或自定义模板，保留原生 sections 与 questions 结构
"""

from typing import Any
from backend.plugin.render_book.schema.payload import RenderDocumentPayload


def adapt_default_payload(payload: RenderDocumentPayload) -> dict[str, Any]:
    """将 RenderDocumentPayload 转换为通用的 dict 上下文"""
    sections_data = []
    for sec in payload.paper.sections or []:
        questions_data = []
        for q in sec.questions or []:
            opts = [f"{opt.key}. {opt.content_text}" for opt in (q.options or [])]
            questions_data.append({
                "no": q.number,
                "stem": q.stem_text,
                "options": opts,
                "answer": q.answer_text,
                "analysis": q.analysis_text,
                "difficulty": q.difficulty,
                "score": q.score,
                "source": q.source_text,
            })
        sections_data.append({
            "title": sec.title,
            "questions": questions_data,
        })

    return {
        "title": payload.book.title,
        "subtitle": payload.book.subtitle,
        "sections": sections_data,
        "metadata": payload.metadata,
        "options": payload.options.model_dump(mode="json") if payload.options else {},
    }
