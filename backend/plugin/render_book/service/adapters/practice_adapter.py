# -*- coding: utf-8 -*-
"""
公考刷题本 (gongkao_practice) 专属数据适配器
负责将 RenderDocumentPayload 适配为刷题专属模板上下文：
1. 个人专属打卡扉页（学员信息、题量、建议用时、自律打卡栏）
2. 双栏题目区（考点微标签、反向设问加粗、作答标记圈、选项 4/2/1 列分栏）
3. 卷末速查参考答案网格（5 列紧凑卡片，极速红笔订正）
4. 深度逐题解析精讲（答案、核心考点、详细解题思路）
"""

import math
from pathlib import Path
import re
from datetime import datetime
from typing import Any

from docxtpl import DocxTemplate

from backend.plugin.render_book.schema.payload import RenderDocumentPayload, RenderQuestionPayload
from backend.plugin.render_book.service.rich_text_parser import (
    parse_material_blocks,
    parse_stem_and_images,
    parse_option_data,
    parse_explanation_and_images,
)
from backend.plugin.render_book.utils.template_catalog import TEMPLATES_ROOT
from backend.utils.timezone import timezone


def highlight_reverse_questions(stem: str) -> list[dict[str, Any]]:
    """智能加粗反向设问词"""
    pattern = r"(不正确的是|不正确|不属于的是|不属于|错误的是|最不恰当的是|最不恰当|不符合的是|不符合|不同的是)"
    parts = re.split(pattern, stem)
    segments = []
    for part in parts:
        if not part:
            continue
        if re.fullmatch(pattern, part):
            segments.append({"text": part, "bold": True})
        else:
            segments.append({"text": part, "bold": False})
    return segments


def calculate_option_columns(options: list[Any]) -> int:
    """根据选项文字长度自适应判断分栏（4 列 / 2 列 / 1 列）"""
    if not options or len(options) != 4:
        return 1
    texts = [f"{opt.get('key', '')}. {opt.get('content', '')}".strip() for opt in options]
    max_len = max(len(t) for t in texts)
    if max_len <= 8:
        return 4
    elif max_len <= 16:
        return 2
    else:
        return 1


PROVINCE_NAMES = [
    "北京", "天津", "上海", "重庆",
    "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东",
    "河南", "湖北", "湖南", "广东", "海南",
    "四川", "贵州", "云南", "陕西", "甘肃", "青海",
    "台湾", "内蒙古", "广西", "西藏", "宁夏", "新疆",
    "深圳", "广州"
]


def extract_source_tag(q: RenderQuestionPayload, material_map: dict[int, Any] | None = None) -> str | None:
    """提取真题来源标签，统一规范为形如【26·国考】、【25·江苏】的紧凑短标签"""
    candidates = []
    if q.source_label:
        candidates.append(q.source_label)
    if q.source_text:
        candidates.append(q.source_text)
    if q.bank_name:
        candidates.append(q.bank_name)
    if q.material_ids and material_map:
        for mid in q.material_ids:
            mat = material_map.get(mid)
            if mat:
                if mat.source_text:
                    candidates.append(mat.source_text)
                if mat.bank_name:
                    candidates.append(mat.bank_name)
    for tag in q.tags:
        if "国考" in tag or "省考" in tag or "联考" in tag or any(p in tag for p in PROVINCE_NAMES):
            candidates.append(tag)

    if not candidates:
        return None

    raw = " ".join(candidates)
    # 如果已经具备形如 26·国考 的模式
    m_direct = re.search(r'(\d{2})[·\.\-]([^\s】\)]+)', raw)
    if m_direct:
        yy, cat = m_direct.group(1), m_direct.group(2)
        cat = cat.replace("真题", "").replace("行测", "").strip()
        return f"{yy}·{cat}"

    # 提取年份
    year_str = None
    m_year_4 = re.search(r'(20\d{2})', raw)
    if m_year_4:
        year_str = m_year_4.group(1)[2:]  # 2026 -> 26
    else:
        m_year_2 = re.search(r'(\d{2})年', raw)
        if m_year_2:
            year_str = m_year_2.group(1)

    # 提取考型 / 地区
    cat_str = None
    if "国考" in raw or "国家公务员" in raw or "中央机关" in raw:
        cat_str = "国考"
    elif "联考" in raw:
        cat_str = "联考"
    else:
        for prov in PROVINCE_NAMES:
            if prov in raw:
                cat_str = "内蒙" if prov == "内蒙古" else prov
                break

    if not cat_str:
        if "事业单位" in raw:
            cat_str = "事业编"
        elif "选调" in raw:
            cat_str = "选调"
        elif "公安" in raw:
            cat_str = "公安"
        elif "省考" in raw:
            cat_str = "省考"

    if year_str and cat_str:
        return f"{year_str}·{cat_str}"
    elif cat_str:
        return cat_str
    elif year_str:
        return f"{year_str}·真题"

    return None


def format_practice_question(
    q: RenderQuestionPayload,
    material_map: dict[int, Any],
    current_material_id: int | None,
    doc: DocxTemplate | None = None,
    mat_questions_map: dict[int, list[int]] | None = None,
) -> tuple[dict[str, Any], int | None]:
    """格式化单道刷题题目，并智能绑定材料、考点标签与来源标签及图文混排内容"""
    # 1. 题干文本与配图提取
    clean_stem, stem_images = parse_stem_and_images(q.stem_text, doc, max_width_mm=120.0)
    stem_segments = highlight_reverse_questions(clean_stem)

    # 提取真题来源标签（如：26·国考、25·江苏）
    source_tag = extract_source_tag(q, material_map)

    # 考点微标签
    kp_label = None
    if q.knowledge_points:
        kp_label = q.knowledge_points[0]
    elif q.tags:
        kp_label = q.tags[0]

    # 2. 选项解析（支持纯图、图文混合与纯文本）
    opts_payload = q.options or []
    parsed_opts = []
    opt_dict = {}
    any_opt_img = False
    for i in range(4):
        if i < len(opts_payload):
            o = opts_payload[i]
            p_opt = parse_option_data(o.content_text, o.key, doc, max_width_mm=30.0)
            parsed_opts.append(p_opt)
            opt_dict[f"opt_{i}"] = f"{o.key}. {p_opt['text']}".strip()
            opt_dict[f"opt_{i}_prefix"] = p_opt["prefix"]
            opt_dict[f"opt_{i}_img"] = p_opt["img"]
            if p_opt["has_img"]:
                any_opt_img = True
        else:
            opt_dict[f"opt_{i}"] = ""
            opt_dict[f"opt_{i}_prefix"] = ""
            opt_dict[f"opt_{i}_img"] = None

    if any_opt_img:
        opt_cols = 2 if len(parsed_opts) <= 4 else 1
    else:
        opt_cols = calculate_option_columns([{"key": p["key"], "content": p["text"]} for p in parsed_opts])

    # 3. 材料题处理
    material_info = None
    new_material_id = current_material_id
    if q.material_ids:
        mat_id = q.material_ids[0]
        if mat_id != current_material_id and mat_id in material_map:
            mat = material_map[mat_id]
            mat_content = mat.content_text or ""
            blocks = parse_material_blocks(mat_content, doc, max_width_mm=135.0)
            raw_lines = [b["text"] for b in blocks if not b["is_img"]]

            # 剔除内容中残留的旧引导语行
            lines = [l for l in raw_lines if not any(kw in l for kw in ("根据以下资料", "根据下列资料", "资料回答"))]

            q_nums = (mat_questions_map or {}).get(mat_id, [])
            if len(q_nums) > 1:
                intro = f"根据以下资料，回答 {min(q_nums)}～{max(q_nums)} 题。"
            elif len(q_nums) == 1:
                intro = f"根据以下资料，回答第 {q_nums[0]} 题。"
            else:
                intro = "根据以下资料，回答问题："

            material_info = {
                "id": mat_id,
                "intro": intro,
                "blocks": blocks,
                "lines": lines,
            }
            new_material_id = mat_id
    else:
        new_material_id = None

    # 4. 解析与解析配图
    clean_exp, analysis_images = parse_explanation_and_images(q.analysis_text, doc, max_width_mm=110.0)

    q_data = {
        "number": q.number,
        "question_id": q.question_id,
        "stem": clean_stem,
        "stem_segments": stem_segments,
        "stem_images": stem_images,
        "source_tag": source_tag,
        "kp_label": kp_label,
        "opt_cols": opt_cols,
        **opt_dict,
        "material": material_info,
        "answer_text": q.answer_text or "暂无",
        "analysis_text": clean_exp,
        "analysis_images": analysis_images,
    }
    return q_data, new_material_id


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
                row_dict[f"c{c}"] = f"{q['number']}. {q['answer_text']}"
            else:
                row_dict[f"c{c}"] = ""
        rows.append(row_dict)
    return rows


def adapt_practice_payload(
    payload: RenderDocumentPayload,
    doc: DocxTemplate | None = None,
    template_file: str | Path | None = None,
) -> dict[str, Any]:
    """将通用载荷适配为【公考刷题本】专用模板上下文"""
    if doc is None:
        if template_file and Path(template_file).exists():
            doc = DocxTemplate(str(template_file))
        else:
            default_tpl = TEMPLATES_ROOT / "gongkao_practice" / "1.0.0" / "template.docx"
            if default_tpl.exists():
                try:
                    doc = DocxTemplate(str(default_tpl))
                except Exception:
                    pass

    meta_dict = payload.metadata or {}

    # 1. 提取学员与打卡信息
    nickname = (
        meta_dict.get("nickname")
        or meta_dict.get("user_name")
        or meta_dict.get("username")
        or "上岸先锋"
    )

    now_dt = timezone.now()
    generated_at = now_dt.strftime("%Y-%m-%d %H:%M")

    # 2. 模块与考点标题识别
    module_title = (
        meta_dict.get("module_title")
        or payload.book.subtitle
        or payload.book.title
        or "行测常考高频专项练习"
    )
    # 清理多余的前缀
    module_title = re.sub(r"^公考[·\s]*", "", module_title).strip()

    # 3. 组织材料映射与题目数据
    material_map = {m.id: m for m in payload.paper.materials}
    parts_context = []
    all_questions = []

    current_mat_id = None
    for sec in payload.paper.sections:
        mat_questions_map: dict[int, list[int]] = {}
        for q in sec.questions:
            if q.material_ids:
                for mid in q.material_ids:
                    mat_questions_map.setdefault(mid, []).append(q.number)

        formatted_qs = []
        for q in sec.questions:
            q_data, current_mat_id = format_practice_question(
                q=q,
                material_map=material_map,
                current_material_id=current_mat_id,
                doc=doc,
                mat_questions_map=mat_questions_map,
            )
            formatted_qs.append(q_data)
            all_questions.append(q_data)

        if formatted_qs:
            parts_context.append({
                "name": sec.title or "专项练习",
                "intro": f"本部分共 {len(formatted_qs)} 道题，请仔细审题并迅速作答：",
                "questions": formatted_qs,
            })

    total_count = len(all_questions)
    # 建议用时：平均 1 分钟 / 题
    suggested_time = max(5, total_count)

    # 4. 汇总考点与题库信息
    bank_name = meta_dict.get("bank_name") or "公务员录用考试标准题库"
    kps = []
    for q in all_questions:
        if q.get("kp_label") and q["kp_label"] not in kps:
            kps.append(q["kp_label"])
    kp_names = "、".join(kps[:2]) if kps else "行测核心考点"
    if len(kps) > 2:
        kp_names += f" 等{len(kps)}个考点"

    # 5. 构建 5 列速查参考答案表格行
    answer_rows = build_answer_rows(all_questions, cols=5)

    return {
        "user": {
            "nickname": nickname,
            "generated_at": generated_at,
        },
        "paper": {
            "module_title": module_title,
            "question_count": total_count,
            "suggested_time": suggested_time,
            "bank_name": bank_name,
            "kp_names": kp_names,
            "parts": parts_context,
            "all_questions": all_questions,
            "answer_rows": answer_rows,
        },
    }
