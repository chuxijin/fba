# -*- coding: utf-8 -*-
"""
基础计算练习本 (basic_calculation) 专属数据适配器
负责将 RenderDocumentPayload 适配为基础计算专属模板上下文：
1. 顶部打卡信息条（练习类型、题量、建议用时、自律打卡栏）
2. 2 列双列速算网格（每行两道题，带算式与作答方框）
3. 卷末 5 列速查参考答案表格
"""

import math
from pathlib import Path
import re
from typing import Any

from docxtpl import DocxTemplate

from backend.plugin.render_book.schema.payload import RenderDocumentPayload


def build_calc_rows(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将题目按 2 列一行组织为 calc_rows"""
    rows = []
    total = len(questions)
    num_rows = math.ceil(total / 2) if total > 0 else 0

    for r in range(num_rows):
        idx0 = r * 2
        idx1 = r * 2 + 1
        q0 = questions[idx0] if idx0 < total else None
        q1 = questions[idx1] if idx1 < total else None

        rows.append({
            "c0_number": q0["number"] if q0 else "",
            "c0_stem": q0["stem_text"] if q0 else "",
            "c1_number": q1["number"] if q1 else "",
            "c1_stem": q1["stem_text"] if q1 else "",
        })
    return rows


def build_box_blocks(questions: list[dict[str, Any]], cols: int = 4) -> list[dict[str, Any]]:
    """将题目按 4 列一行组织为数据盒 block（用于基期量、增长量等）"""
    blocks = []
    total = len(questions)
    num_blocks = math.ceil(total / cols) if total > 0 else 0

    for b in range(num_blocks):
        block_dict = {}
        for c in range(cols):
            idx = b * cols + c
            if idx < total:
                q = questions[idx]
                block_dict[f"c{c}_num"] = q["number"]
                block_dict[f"c{c}_stem"] = q["stem_text"]
            else:
                block_dict[f"c{c}_num"] = ""
                block_dict[f"c{c}_stem"] = ""
        blocks.append(block_dict)
    return blocks


def build_compare_blocks(questions: list[dict[str, Any]], cols: int = 2) -> list[dict[str, Any]]:
    """将题目按 2 列一行组织为分数大小比较数据盒 block"""
    blocks = []
    total = len(questions)
    num_blocks = math.ceil(total / cols) if total > 0 else 0

    for b in range(num_blocks):
        block_dict = {}
        for c in range(cols):
            idx = b * cols + c
            if idx < total:
                q = questions[idx]
                block_dict[f"c{c}_num"] = q["number"]
                block_dict[f"c{c}_stem"] = q["stem_text"]
            else:
                block_dict[f"c{c}_num"] = ""
                block_dict[f"c{c}_stem"] = ""
        blocks.append(block_dict)
    return blocks


def build_answer_rows(questions: list[dict[str, Any]], cols: int = 5) -> list[dict[str, str]]:
    """生成 5 列网格速查答案表格数据"""
    rows = []
    total = len(questions)
    num_rows = math.ceil(total / cols) if total > 0 else 0

    for r in range(num_rows):
        row_dict = {}
        for c in range(cols):
            idx = r * cols + c
            if idx < total:
                q = questions[idx]
                ans = q.get("answer_text", "")
                row_dict[f"c{c}"] = f"{q['number']}、{ans}"
            else:
                row_dict[f"c{c}"] = ""
        rows.append(row_dict)
    return rows


def xml_safe_str(s: str) -> str:
    """将文本中的半角 < 和 > 转为全角 ＜ 和 ＞，避免破坏 WordprocessingML XML 结构"""
    if not s:
        return ""
    return str(s).replace("<", "＜").replace(">", "＞")


def adapt_basic_calc_payload(
    payload: RenderDocumentPayload,
    doc: DocxTemplate | None = None,
    template_file: str | Path | None = None,
) -> dict[str, Any]:
    """将通用载荷适配为【基础计算与资料分析专项练习本】专用模板上下文"""
    meta_dict = payload.metadata or {}

    # 1. 提取题目与分节（兼容 paper.sections 与 metadata.questions）
    sections_context = []
    all_questions = []

    # 优先检查 paper.sections
    if payload.paper and payload.paper.sections:
        global_num = 1
        for sec in payload.paper.sections:
            sec_qs = []
            for q in sec.questions:
                stem = q.stem_text or ""
                # 清洗多余 html
                stem = re.sub(r"<[^>]+>", "", stem).strip()
                ans = xml_safe_str(q.answer_text or "")
                sec_qs.append({
                    "number": global_num,
                    "stem_text": stem,
                    "answer_text": ans,
                })
                all_questions.append({
                    "number": global_num,
                    "stem_text": stem,
                    "answer_text": ans,
                })
                global_num += 1

            if sec_qs:
                is_compare = (
                    "compare" in sec.key
                    or "比大小" in (sec.title or "")
                    or "比较" in (sec.title or "")
                )
                is_data_box = (
                    not is_compare
                    and (
                        sec.key.startswith("box")
                        or "data_box" in sec.key
                        or "sec_data" in sec.key
                        or "数据盒" in (sec.title or "")
                        or "资料分析" in (sec.title or "")
                        or "基期" in (sec.title or "")
                        or "增长" in (sec.title or "")
                    )
                )
                calc_rows = build_calc_rows(sec_qs) if (not is_compare and not is_data_box) else []
                box_blocks = build_box_blocks(sec_qs, cols=4) if is_data_box else []
                compare_blocks = build_compare_blocks(sec_qs, cols=2) if is_compare else []

                safe_title = xml_safe_str(sec.title or "")
                sections_context.append({
                    "title": safe_title,
                    "hint": "",
                    "calc_rows": calc_rows,
                    "box_blocks": box_blocks,
                    "compare_blocks": compare_blocks,
                })
    elif "questions" in meta_dict and isinstance(meta_dict["questions"], list):
        sec_qs = []
        for idx, item in enumerate(meta_dict["questions"], start=1):
            stem = str(item.get("stem", item.get("stem_text", ""))).strip()
            ans = str(item.get("answer", item.get("answer_text", ""))).strip()
            q_data = {"number": idx, "stem_text": stem, "answer_text": ans}
            sec_qs.append(q_data)
            all_questions.append(q_data)

        sections_context.append({
            "title": meta_dict.get("type_title", "基础计算速练"),
            "hint": meta_dict.get("type_hint", ""),
            "calc_rows": build_calc_rows(sec_qs),
            "box_blocks": [],
            "compare_blocks": [],
        })

    total_count = len(all_questions)
    # 建议用时：平均 30 秒 1 题
    suggested_time = max(3, math.ceil(total_count * 0.5))

    # 2. 判断是否显示答案
    show_answers = False
    if hasattr(payload, "options") and payload.options and payload.options.include_answer:
        show_answers = True
    elif hasattr(payload, "render_plan") and payload.render_plan:
        if payload.render_plan.content_mode == "questions_with_answers" or payload.render_plan.solution_mode in {"inline", "appendix"}:
            show_answers = True

    # 3. 构建答案速查行
    answer_rows = build_answer_rows(all_questions, cols=5)

    return {
        "book": {
            "title": payload.book.title or "基础计算与速算专项练习",
            "subtitle": payload.book.subtitle or "资料分析极速直除 · 核心数字敏感度强化",
        },
        "paper": {
            "question_count": total_count,
            "suggested_time": suggested_time,
            "sections": sections_context,
            "show_answers": show_answers,
            "answer_rows": answer_rows,
        },
    }
