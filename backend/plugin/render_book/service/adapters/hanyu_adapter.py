# -*- coding: utf-8 -*-
"""
汉语词汇手册 (hanyu) 专属数据适配器
负责将 RenderDocumentPayload 适配为汉语词汇手册专属模板上下文：
1. 封面概览（词汇总量、学员姓名、打卡状态）
2. 结构化词汇精讲卡片：
   - 词名、拼音、褒贬色彩微标签、公考考频
   - 精炼释义、经典例句、近反义词辨析、典故出处
"""

from pathlib import Path
import re
from typing import Any

from docxtpl import DocxTemplate

from backend.plugin.render_book.schema.payload import RenderDocumentPayload


def clean_text(val: Any) -> str:
    """提取与清理纯文本内容"""
    if not val:
        return ""
    if isinstance(val, str):
        t = re.sub(r"<[^>]+>", "", val).strip()
        return t
    if isinstance(val, list):
        items = [clean_text(x) for x in val if clean_text(x)]
        return "；".join(items)
    if isinstance(val, dict):
        if "text" in val:
            return clean_text(val["text"])
        if "meaning" in val:
            return clean_text(val["meaning"])
        parts = []
        for k, v in val.items():
            ct = clean_text(v)
            if ct:
                parts.append(f"{k}：{ct}" if k not in ("text", "meaning") else ct)
        return "；".join(parts)
    return str(val).strip()


def format_hanyu_word(raw: Any) -> dict[str, Any]:
    """格式化单个词语数据"""
    if isinstance(raw, dict):
        name = raw.get("name") or raw.get("word") or ""
        pinyin = raw.get("pinyin") or ""
        baobian = raw.get("baobian") or ""
        freq = raw.get("frequency") or 0

        # 释义
        def_val = raw.get("definition_info") or raw.get("detail_means") or raw.get("definition") or ""
        definition = clean_text(def_val)

        # 例句
        liju_raw = raw.get("liju") or raw.get("examples") or ""
        if isinstance(liju_raw, list) and liju_raw:
            first_ex = liju_raw[0]
            liju = clean_text(first_ex)
        else:
            liju = clean_text(liju_raw)

        # 近义词 / 反义词
        syns = clean_text(raw.get("synonyms") or raw.get("near_synonyms"))
        ants = clean_text(raw.get("antonym") or raw.get("antonyms"))

        # 出处
        chuchu = clean_text(raw.get("chu_chu") or raw.get("chuchu") or raw.get("source"))

        return {
            "name": name,
            "pinyin": pinyin,
            "baobian": baobian,
            "frequency": freq if freq and int(freq) > 0 else None,
            "definition": definition,
            "liju": liju,
            "synonyms": syns,
            "antonym": ants,
            "chuchu": chuchu,
        }
    else:
        # 兼容 Pydantic 对象
        name = getattr(raw, "name", "")
        pinyin = getattr(raw, "pinyin", "")
        baobian = getattr(raw, "baobian", "")
        freq = getattr(raw, "frequency", 0)
        definition = clean_text(getattr(raw, "definition_info", None) or getattr(raw, "detail_means", None))
        liju_raw = getattr(raw, "liju", None)
        liju = clean_text(liju_raw[0]) if (isinstance(liju_raw, list) and liju_raw) else clean_text(liju_raw)
        syns = clean_text(getattr(raw, "synonyms", None))
        ants = clean_text(getattr(raw, "antonym", None))
        chuchu = clean_text(getattr(raw, "chu_chu", None))

        return {
            "name": name,
            "pinyin": pinyin,
            "baobian": baobian,
            "frequency": freq if freq and int(freq) > 0 else None,
            "definition": definition,
            "liju": liju,
            "synonyms": syns,
            "antonym": ants,
            "chuchu": chuchu,
        }


def adapt_hanyu_payload(
    payload: RenderDocumentPayload,
    doc: DocxTemplate | None = None,
    template_file: str | Path | None = None,
) -> dict[str, Any]:
    """将通用载荷适配为【汉语词汇手册】专用模板上下文"""
    meta_dict = payload.metadata or {}

    words_context = []

    # 1. 优先提取 paper.sections 中的 words
    if payload.paper and payload.paper.sections:
        for sec in payload.paper.sections:
            sec_words = getattr(sec, "words", []) or []
            for w in sec_words:
                fw = format_hanyu_word(w)
                if fw["name"]:
                    words_context.append(fw)

    # 2. 检查 paper.words
    if not words_context and payload.paper:
        paper_words = getattr(payload.paper, "words", []) or []
        for w in paper_words:
            fw = format_hanyu_word(w)
            if fw["name"]:
                words_context.append(fw)

    # 3. 检查 metadata.words
    if not words_context and "words" in meta_dict and isinstance(meta_dict["words"], list):
        for w in meta_dict["words"]:
            fw = format_hanyu_word(w)
            if fw["name"]:
                words_context.append(fw)

    nickname = (
        meta_dict.get("nickname")
        or meta_dict.get("user_name")
        or meta_dict.get("username")
        or "公务员考生"
    )

    return {
        "book": {
            "title": payload.book.title or "公考高频汉语词汇手册",
            "subtitle": payload.book.subtitle or "成语深度辨析 · 考点精准释义 · 典型语境例句",
        },
        "metadata": {
            "nickname": nickname,
        },
        "paper": {
            "total_count": len(words_context),
            "words": words_context,
        },
    }
