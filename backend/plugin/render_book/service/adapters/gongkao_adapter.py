# -*- coding: utf-8 -*-
"""
公考（国考/省考）行测真题卷专属数据适配器
严格遵循新大纲官方六大模块规范与考场排版标准：
1. 政治理论
2. 常识判断
3. 言语理解与表达
4. 数量关系
5. 判断推理
6. 资料分析
"""

import re
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate

from backend.plugin.render_book.schema.payload import RenderDocumentPayload, RenderQuestionPayload
from backend.plugin.render_book.service.rich_text_parser import (
    parse_material_blocks,
    parse_stem_and_images,
    parse_option_data,
)
from backend.plugin.render_book.utils.template_catalog import TEMPLATES_ROOT

# 国考新大纲官方六大标准模块规范（严格匹配真题官方规范）
GONGKAO_STANDARD_MODULES = [
    {
        "key": "zhengzhi",
        "title": "政治理论",
        "intro": "根据题目要求，在四个选项中选出一个最恰当的答案。",
        "default_time": 10,
    },
    {
        "key": "changshi",
        "title": "常识判断",
        "intro": "根据题目要求，在四个选项中选出一个最恰当的答案。",
        "default_time": 10,
    },
    {
        "key": "yanyu",
        "title": "言语理解与表达",
        "intro": "本部分包含表达与理解两方面的内容。请在四个选项中选出一个最恰当的答案。",
        "default_time": 35,
    },
    {
        "key": "shuliang",
        "title": "数量关系",
        "intro": "在这部分试题中，每道题呈现一段表达数字关系的文字，要求你迅速准确地计算出答案。",
        "default_time": 15,
    },
    {
        "key": "panduan",
        "title": "判断推理",
        "intro": "本部分包含图形推理、定义判断、类比推理与逻辑判断四种类型的试题。请在四个选项中选出一个最恰当的答案。",
        "default_time": 35,
    },
    {
        "key": "ziliao",
        "title": "资料分析",
        "intro": "所给出的图、表、文字或综合性资料均有若干个问题要你回答。你应根据资料提供的信息进行分析、比较、计算和判断处理。",
        "default_time": 25,
    },
]

CN_NUMS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

PROVINCE_NAMES = {
    '北京': '北京市', '天津': '天津市', '上海': '上海市', '重庆': '重庆市',
    '河北': '河北省', '山西': '山西省', '辽宁': '辽宁省', '吉林': '吉林省',
    '黑龙江': '黑龙江省', '江苏': '江苏省', '浙江': '浙江省', '安徽': '安徽省',
    '福建': '福建省', '江西': '江西省', '山东': '山东省', '河南': '河南省',
    '湖北': '湖北省', '湖南': '湖南省', '广东': '广东省', '海南': '海南省',
    '四川': '四川省', '贵州': '贵州省', '云南': '云南省', '陕西': '陕西省',
    '甘肃': '甘肃省', '青海': '青海省', '台湾': '台湾省',
    '内蒙古': '内蒙古自治区', '广西': '广西壮族自治区', '西藏': '西藏自治区',
    '宁夏': '宁夏回族自治区', '新疆': '新疆维吾尔自治区'
}


def resolve_gongkao_cover(
    title: str | None,
    metadata: dict[str, Any] | None = None,
    filters: dict[str, Any] | None = None,
) -> tuple[str, str, str]:
    """智能解析与矫正公考（国考/省考）封面三要素：
    1. exam_name: 考卷全称抬头（如：2027年中央机关及其直属机构考试录用公务员笔试、江苏省2026年考试录用公务员笔试）
    2. subject_title: 科目名称（固定：行政职业能力测验）
    3. category: 试卷类别（如：行政执法类、副省级、地市类、A类、B类、C类等）
    """
    metadata = metadata or {}
    filters = filters or {}
    raw_title = (title or metadata.get("exam_name") or metadata.get("title") or "").strip()

    # 1. 提取年份 (如 2026, 2027)
    explicit_year = metadata.get("exam_year") or metadata.get("year") or filters.get("year")
    if explicit_year and str(explicit_year).isdigit():
        year = str(explicit_year).strip()
    else:
        year_match = re.search(r"((?:19|20)\d{2})", raw_title)
        year = year_match.group(1) if year_match else "2026"

    # 2. 类别识别与智能规范化
    explicit_cat = metadata.get("category") or metadata.get("exam_category") or filters.get("category")
    category = str(explicit_cat).strip() if explicit_cat else ""

    if not category:
        # 省考 A/B/C 类（支持如 A类, （A类）, A卷, 综合A类）
        abc_match = re.search(r"[（(]?\s*([ABCabc])\s*(?:类|卷)\s*[)）]?", raw_title)
        if abc_match:
            category = f"{abc_match.group(1).upper()}类"
        elif "行政执法" in raw_title or "执法" in raw_title:
            category = "行政执法类"
        elif "副省级" in raw_title or "副省" in raw_title or "省级以上" in raw_title or "综合管理" in raw_title:
            category = "副省级"
        elif "地市" in raw_title or "市地" in raw_title or "市级以下" in raw_title:
            category = "地市类"
        elif "县乡" in raw_title or "乡镇" in raw_title:
            category = "县乡类"
        elif "公安" in raw_title:
            category = "公安专业类"

    # 3. 考卷主抬头 (exam_name) 智能规范化与矫正
    # 如果用户已经传入了官方标准的完整全称（例如：2027年中央机关及其直属机构考试录用公务员笔试），直接予以尊重
    if "中央机关" in raw_title and "笔试" in raw_title:
        exam_name = raw_title
    elif "考试录用公务员笔试" in raw_title:
        exam_name = raw_title
    elif "国考" in raw_title or "国家公务员" in raw_title or "中央机关" in raw_title:
        # 国考统一标准抬头规范
        exam_name = f"{year}年中央机关及其直属机构考试录用公务员笔试"
    else:
        # 匹配省份
        found_province = None
        for p_short, p_full in PROVINCE_NAMES.items():
            if p_short in raw_title:
                found_province = p_full
                break

        if found_province:
            # 省考统一标准抬头规范，如：江苏省2026年考试录用公务员笔试
            exam_name = f"{found_province}{year}年考试录用公务员笔试"
        elif "省考" in raw_title:
            exam_name = f"{year}年地方考试录用公务员笔试"
        else:
            # 默认作为国考标准全称
            exam_name = f"{year}年中央机关及其直属机构考试录用公务员笔试"

    # 4. 清理考卷抬头中的多余括号、科目名及噪音词（确保顶头单行规范、不被分类挤占换行）
    clean_exam_name = re.sub(r"[（(].*?[)）]", "", exam_name)
    clean_exam_name = re.sub(r"《.*?》", "", clean_exam_name)
    for noise in ("行政职业能力测验", "行测真题", "行测", "真题卷", "真题", "试卷"):
        clean_exam_name = clean_exam_name.replace(noise, "")
    clean_exam_name = clean_exam_name.strip()
    if clean_exam_name:
        exam_name = clean_exam_name

    return exam_name, "行政职业能力测验", category



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


def format_question_for_docx(
    q: RenderQuestionPayload,
    material_map: dict[int, Any] | None = None,
    current_material_id: int | None = None,
    doc: DocxTemplate | None = None,
    mat_questions_map: dict[int, list[int]] | None = None,
) -> tuple[dict[str, Any], int | None]:
    """
    格式化单道试题供 Word 模板渲染：
    - 选项智能分栏（4列/2列/1列）；
    - 题干设问词加粗与题干插图提取；
    - 材料题结构化图文混排（blocks）；
    - 选项支持纯图、图文混合与纯文本；
    - 仅在材料大题的首题挂载材料，避免小题重复输出材料；
    - 材料引导语严格采用官方规范：“根据以下资料，回答 X～Y 题。”。
    """
    def visual_len(text: str) -> float:
        return sum(1.0 if ord(c) > 127 else 0.5 for c in text)

    # 1. 题干纯文本（加粗设问词）与题干插图列表
    clean_stem, stem_images = parse_stem_and_images(q.stem_text, doc, max_width_mm=120.0)
    stem_segments = highlight_reverse_questions(clean_stem)

    # 2. 选项解析
    opts_payload = q.options or []
    parsed_opts = []
    formatted_opts = []
    for opt in opts_payload:
        p_opt = parse_option_data(opt.content_text, opt.key, doc, max_width_mm=30.0)
        parsed_opts.append(p_opt)
        formatted_opts.append(f"{opt.key}. {p_opt['text']}".strip())

    max_len = max((visual_len(text) for text in formatted_opts), default=0.0)
    any_opt_img = any(p["has_img"] for p in parsed_opts)

    if any_opt_img:
        layout = "2col" if len(parsed_opts) <= 4 else "1col"
    elif max_len <= 6.0 and len(formatted_opts) == 4:
        layout = "4col"
    elif max_len <= 14.0 and len(formatted_opts) == 4:
        layout = "2col"
    else:
        layout = "1col"

    # 3. 材料处理：如果本题有材料且与上一题不同，才输出材料
    norm_material = None
    new_material_id = current_material_id
    if q.material_ids and material_map:
        mat_id = q.material_ids[0]
        if mat_id != current_material_id and mat_id in material_map:
            mat = material_map[mat_id]
            new_material_id = mat_id
            # 解析为文字段落与居中图片段落
            blocks = parse_material_blocks(mat.content_text, doc, max_width_mm=135.0)
            text_lines = [b["text"] for b in blocks if not b["is_img"]]

            # 严格计算官方引导语（形如：“根据以下资料，回答 126～130 题。”）
            q_nums = (mat_questions_map or {}).get(mat_id, [])
            if len(q_nums) > 1:
                intro = f"根据以下资料，回答 {min(q_nums)}～{max(q_nums)} 题。"
            elif len(q_nums) == 1:
                intro = f"根据以下资料，回答第 {q_nums[0]} 题。"
            else:
                intro = "根据以下资料，回答问题："

            norm_material = {
                "intro": intro,
                "blocks": blocks,
                "lines": text_lines,
            }

    q_data: dict[str, Any] = {
        "no": q.number,
        "material": norm_material,
        "stem_segments": stem_segments,
        "stem_images": stem_images,
        "layout": layout,
        "raw_options": formatted_opts,
    }

    for i, p_opt in enumerate(parsed_opts):
        q_data[f"opt_{i}"] = formatted_opts[i]
        q_data[f"opt_{i}_prefix"] = p_opt["prefix"]
        q_data[f"opt_{i}_img"] = p_opt["img"]

    return q_data, new_material_id


def adapt_gongkao_payload(
    payload: RenderDocumentPayload,
    doc: DocxTemplate | None = None,
    template_file: str | Path | None = None,
) -> dict[str, Any]:
    """
    将 RenderDocumentPayload 适配转换为公考行测真题专属 Word 上下文：
    1. 严格映射新大纲官方六大模块；
    2. 过滤无题目的模块，按实际内容顺延编号（第一部分、第二部分...）；
    3. 自动匹配官方前置指导语与“请开始答题：”；
    4. 自动生成模块间过渡语与卷末结束语；
    5. 全面支持图文混排（材料图表、题干图、选项图）。
    """
    if doc is None:
        if template_file and Path(template_file).exists():
            doc = DocxTemplate(str(template_file))
        else:
            default_tpl = TEMPLATES_ROOT / "gongkao_xingce" / "1.0.0" / "template.docx"
            if default_tpl.exists():
                try:
                    doc = DocxTemplate(str(default_tpl))
                except Exception:
                    pass

    material_map = {m.id: m for m in (payload.paper.materials or [])}

    # 1. 将题目按所属模块分类
    sections = payload.paper.sections or []
    # 建立分类桶
    categorized_questions: dict[str, list[RenderQuestionPayload]] = {
        std["key"]: [] for std in GONGKAO_STANDARD_MODULES
    }
    other_sections: list[tuple[str, list[RenderQuestionPayload]]] = []

    for sec in sections:
        sec_title = sec.title.strip()
        matched_key = None
        for std in GONGKAO_STANDARD_MODULES:
            if std["title"] in sec_title or sec_title in std["title"]:
                matched_key = std["key"]
                break
        if matched_key:
            categorized_questions[matched_key].extend(sec.questions or [])
        else:
            other_sections.append((sec_title, sec.questions or []))

    # 2. 组装非空标准模块
    active_parts_data: list[dict[str, Any]] = []
    for std in GONGKAO_STANDARD_MODULES:
        qs = categorized_questions[std["key"]]
        if qs:
            active_parts_data.append({
                "title": std["title"],
                "intro": std["intro"],
                "time_limit": std["default_time"],
                "raw_questions": qs,
            })

    # 处理未匹配到标准模块的其他章节
    for title, qs in other_sections:
        if qs:
            active_parts_data.append({
                "title": title,
                "intro": "根据题目要求，在四个选项中选出一个最恰当的答案。",
                "time_limit": 15,
                "raw_questions": qs,
            })

    # 3. 顺延编号并格式化题目
    total_parts = len(active_parts_data)
    parts_context = []

    current_material_id = None
    for idx, part_data in enumerate(active_parts_data, start=1):
        cn_idx = CN_NUMS[idx - 1] if idx <= len(CN_NUMS) else str(idx)
        clean_title = re.sub(r"^第[一二三四五六七八九十0-9]+部分\s*", "", part_data["title"]).strip()
        part_name = f"第{cn_idx}部分 {clean_title}"

        intro = part_data["intro"]
        if not intro.endswith("请开始答题："):
            intro = f"{intro}\n请开始答题："

        if idx < total_parts:
            next_cn = CN_NUMS[idx] if idx < len(CN_NUMS) else str(idx + 1)
            end_notice = f"※※※第{cn_idx}部分结束，请继续做第{next_cn}部分！※※※"
        else:
            end_notice = "※※※全部测验到此结束！※※※"

        # 预先扫描本部分材料关联的题目题号范围
        mat_questions_map: dict[int, list[int]] = {}
        for q in part_data["raw_questions"]:
            if q.material_ids:
                for mid in q.material_ids:
                    mat_questions_map.setdefault(mid, []).append(q.number)

        formatted_questions = []
        for q in part_data["raw_questions"]:
            q_ctx, current_material_id = format_question_for_docx(
                q=q,
                material_map=material_map,
                current_material_id=current_material_id,
                doc=doc,
                mat_questions_map=mat_questions_map,
            )
            formatted_questions.append(q_ctx)

        parts_context.append({
            "name": part_name,
            "question_count": len(formatted_questions),
            "time_limit": part_data["time_limit"],
            "intro": intro,
            "end_notice": end_notice,
            "questions": formatted_questions,
        })

    # 4. 智能矫正公考试卷封面三要素（抬头考卷全称、科目名、试卷类别）
    meta_dict = payload.metadata or {}
    exam_name, subject_title, category = resolve_gongkao_cover(
        title=payload.book.title,
        metadata=meta_dict,
        filters=meta_dict.get("filters", {}),
    )
    return {
        "paper": {
            "exam_name": exam_name,
            "title": subject_title,
            "category": category,
            "parts": parts_context,
        }
    }

