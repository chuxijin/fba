# -*- coding: utf-8 -*-
"""
富文本结构化解析器
将 HTML 富文本内容（材料、题干、选项、解析）精准拆解为结构化图文段落块，
彻底告别简单粗暴的正则标签剥离，全面赋能真卷与刷题本的高清图文混排。
"""

import re
from typing import Any
from docxtpl import DocxTemplate, InlineImage

from backend.plugin.render_book.service.image_manager import ImageManager, image_manager

# 匹配 <img> 标签并提取 src
IMG_TAG_PATTERN = re.compile(
    r'<img\s+[^>]*?src=["\'](?P<src>[^"\']+)["\'][^>]*?>',
    re.IGNORECASE | re.DOTALL
)

# 已知行内微型逻辑/公式符号图片的特征 Hash 或标识
KNOWN_SYMBOL_HASHES = {
    "22356dff5dbcdc4c37e6632600979a0e": " → ",
    "abe086ab947f7a5b37c464c4ce74f115": " — ",
}


def normalize_inline_symbol_images(html_text: str | None) -> str:
    """
    将 HTML 中的行内微型逻辑推导/公式符号图片（如箭头、横线等）转换为标准文本字符，
    避免原本的推导逻辑被暴力清洗抹除，同时防止其被错误当成大配图独占成行渲染。
    """
    if not html_text:
        return ""

    def _replace_img(match: re.Match) -> str:
        tag = match.group(0)
        src = match.group(1) or ""
        alt_match = re.search(r'alt=["\']([^"\']+)["\']', tag, re.IGNORECASE)
        alt = alt_match.group(1).strip() if alt_match else ""

        # 1. 匹配已知 Hash
        for h, sym in KNOWN_SYMBOL_HASHES.items():
            if h in src:
                return sym

        # 2. 匹配 alt 属性
        if alt:
            if alt in ["→", "->", "=>", "arrow"]:
                return " → "
            if alt in ["—", "-", "--", "dash"]:
                return " — "
            if any(k in alt.lower() for k in ["arrow", "推导", "箭头"]):
                return " → "

        # 3. 匹配 URL 关键字
        lower_src = src.lower()
        if any(k in lower_src for k in ["arrow", "rightarrow"]):
            return " → "
        if any(k in lower_src for k in ["dash", "line"]):
            return " — "

        # 其他常规图片保持原样，交给后续配图逻辑处理
        return tag

    # 替换 <img ... src="..." ...>
    return re.sub(
        r'<img\s+[^>]*?src=["\']([^"\']+)["\'][^>]*?>',
        _replace_img,
        html_text,
        flags=re.IGNORECASE,
    )


def clean_html_text_only(text: str | None) -> str:
    """清理 HTML 标签，返回纯净文本（剥离图片标签及格式噪音，保留行内符号与填空横线）"""
    if not text:
        return ""
    # 保护填空挖空：将 <u> 内包含的空白占位符转换为公考标准下划线横线
    s = re.sub(r'<u[^>]*>[\s\u00a0\xa0&nbsp;]*</u>', '______', text, flags=re.IGNORECASE)
    # 先将微型推导符号/箭头图片就地转为纯文本字符
    s = normalize_inline_symbol_images(s)
    s = re.sub(r'<\s*br\s*/?>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'</\s*p\s*>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'</\s*div\s*>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'<[^>]+>', '', s)
    s = s.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in s.split('\n')]
    # 出版级两端对齐优化：换行符前注入制表符 \t\n，使 Word/WPS 在软换行时制表符吸收行尾空白，彻底消除短行被拉伸分散
    return '\t\n'.join([line for line in lines if line])


def clean_opt_text_only(text: str | None, key: str) -> str:
    """清理选项文本并去除冗余的选项编号前缀（如 A.、A、A:）"""
    cleaned = clean_html_text_only(text).replace('\t', '')
    return re.sub(rf'^{re.escape(key)}[\.\、\s\:\：]+', '', cleaned, flags=re.IGNORECASE).strip()


def extract_image_urls(html_text: str | None) -> list[str]:
    """提取 HTML 中的所有题目配图 URL 列表（自动剔除已转为文本的微型符号图标）"""
    if not html_text:
        return []
    urls = []
    for m in IMG_TAG_PATTERN.finditer(html_text):
        src = m.group("src").strip()
        if not src:
            continue
        # 过滤已知符号图片，绝不让其作为独立段落配图
        if any(h in src for h in KNOWN_SYMBOL_HASHES):
            continue
        lower_src = src.lower()
        if any(k in lower_src for k in ["arrow", "rightarrow", "dash"]):
            continue
        urls.append(src)
    return urls


def parse_material_blocks(
    content_html: str | None,
    doc: DocxTemplate,
    img_mgr: ImageManager | None = None,
    max_width_mm: float = 135.0,
) -> list[dict[str, Any]]:
    """
    将材料 HTML 拆解为图文交织的结构化块列表：
    - {'is_img': False, 'text': '文字段落'}
    - {'is_img': True, 'img': InlineImage}
    """
    if not content_html:
        return []

    mgr = img_mgr or image_manager
    blocks: list[dict[str, Any]] = []

    # 按照 <img> 标签将内容分片
    last_idx = 0
    for match in IMG_TAG_PATTERN.finditer(content_html):
        # 1. 匹配点前面的文字部分
        text_chunk = content_html[last_idx:match.start()]
        cleaned_text = clean_html_text_only(text_chunk)
        if cleaned_text:
            for line in cleaned_text.split('\n'):
                line = line.strip()
                if line:
                    blocks.append({"is_img": False, "text": line})

        # 2. 匹配到的图片
        img_url = match.group("src").strip()
        inline_img = mgr.create_inline_image(doc, img_url, max_width_mm=max_width_mm)
        if inline_img:
            blocks.append({"is_img": True, "img": inline_img})

        last_idx = match.end()

    # 3. 最后一个图片后面的剩余文字
    remaining_text = content_html[last_idx:]
    cleaned_rem = clean_html_text_only(remaining_text)
    if cleaned_rem:
        for line in cleaned_rem.split('\n'):
            line = line.strip()
            if line:
                blocks.append({"is_img": False, "text": line})

    return blocks


def highlight_reverse_questions(stem: str) -> list[dict[str, Any]]:
    """智能加粗反向设问词"""
    pattern = r"(不正确的是|不正确|不属于的是|不属于|错误的是|最不恰当的是|最不恰当|不符合的是|不符合|不同的是)"
    parts = re.split(pattern, stem)
    segments = []
    for part in parts:
        if not part:
            continue
        bold = bool(re.fullmatch(pattern, part))
        segments.append({"text": part, "bold": bold, "is_img": False})
    return segments


def parse_stem_structure(
    stem_html: str | None,
    doc: DocxTemplate,
    img_mgr: ImageManager | None = None,
    max_width_mm: float = 120.0,
) -> tuple[list[dict[str, Any]], list[InlineImage], str]:
    """
    结构化解析题干图文（第一性原理：区分行内微型公式与块级大配图）：
    - 行内微型公式图片（如数学分数 1/4、1/3、根号等）：作为 InlineImage 嵌入 stem_segments，高度适配文字行高 (4.8mm)；
    - 块级大配图（如几何图形、函数图表）：放入 stem_images 作为独立段落居中输出；
    - 反向设问词智能加粗不受图文拆分影响。
    返回: (stem_segments, stem_images, clean_stem_text)
    """
    if not stem_html:
        return [], [], ""

    from docx.shared import Mm
    from PIL import Image

    mgr = img_mgr or image_manager
    stem_segments: list[dict[str, Any]] = []
    stem_images: list[InlineImage] = []
    text_pieces: list[str] = []
    last_idx = 0

    for match in IMG_TAG_PATTERN.finditer(stem_html):
        # 1. 前置文字片段处理
        text_chunk = stem_html[last_idx:match.start()]
        cleaned = clean_html_text_only(text_chunk)
        if cleaned:
            stem_segments.extend(highlight_reverse_questions(cleaned))
            text_pieces.append(cleaned)

        # 2. 图片属性分析与分流
        tag = match.group(0)
        src = match.group("src").strip()

        # 判定是否属于行内公式特征 (flag="tex" 或 formulas URL 或尺寸微小)
        is_formula = 'flag="tex"' in tag or "flag='tex'" in tag or '/accessories/formulas' in src or '/formulas' in src

        local_path = mgr.get_local_path(src)
        if local_path and local_path.exists():
            try:
                with Image.open(local_path) as im:
                    w_px, h_px = im.size
                if is_formula or (0 < h_px <= 65 and 0 < w_px <= 300):
                    # 行内公式图片：高度等比约为 4.8mm（刚好适配 10.5pt 字号），段落内流式插入
                    inline_formula = InlineImage(doc, str(local_path), height=Mm(4.8))
                    stem_segments.append({"is_img": True, "img": inline_formula, "bold": False, "text": ""})
                else:
                    # 块级大配图：独占段落居中
                    block_img = mgr.create_inline_image(doc, src, max_width_mm=max_width_mm)
                    if block_img:
                        stem_images.append(block_img)
            except Exception as e:
                logger.warning(f"题干图片解析异常: {src}, {e}")

        last_idx = match.end()

    # 3. 尾部剩余文字处理
    rem_chunk = stem_html[last_idx:]
    cleaned_rem = clean_html_text_only(rem_chunk)
    if cleaned_rem:
        stem_segments.extend(highlight_reverse_questions(cleaned_rem))
        text_pieces.append(cleaned_rem)

    full_clean_text = "".join(text_pieces)
    return stem_segments, stem_images, full_clean_text


def parse_stem_and_images(
    stem_html: str | None,
    doc: DocxTemplate,
    img_mgr: ImageManager | None = None,
    max_width_mm: float = 120.0,
) -> tuple[str, list[InlineImage]]:
    """
    兼容旧调用接口：解析题干并返回 (纯文本题干, 题干配图列表)
    """
    _, images, text = parse_stem_structure(stem_html, doc, img_mgr, max_width_mm)
    return text, images


def parse_option_data(
    opt_html: str | None,
    key: str,
    doc: DocxTemplate,
    img_mgr: ImageManager | None = None,
    max_width_mm: float = 35.0,
) -> dict[str, Any]:
    """
    解析选项内容：
    返回 {'key': 'A', 'prefix': 'A.', 'text': '文字', 'img': InlineImage or None, 'has_img': bool}
    """
    mgr = img_mgr or image_manager
    clean_text = clean_opt_text_only(opt_html, key)
    img_urls = extract_image_urls(opt_html)

    inline_img = None
    if img_urls:
        inline_img = mgr.create_inline_image(doc, img_urls[0], max_width_mm=max_width_mm)

    return {
        "key": key,
        "prefix": f"{key}.",
        "text": clean_text,
        "img": inline_img,
        "has_img": inline_img is not None,
    }


def parse_analysis_structure(
    exp_html: str | None,
    doc: DocxTemplate,
    img_mgr: ImageManager | None = None,
    max_width_mm: float = 110.0,
) -> tuple[list[dict[str, Any]], list[InlineImage], str]:
    """
    结构化解析题目解析图文流（第一性原理：区分行内微型公式与块级大配图）：
    - 行内公式小图（flag="tex"、formulas 或高度 <= 90px 算式）：嵌入 analysis_segments，流式内联于文字流中；
    - 块级大图（如几何图解）：放入 analysis_images，独立段落居中展示；
    返回: (analysis_segments, analysis_images, clean_text)
    """
    if not exp_html:
        return [{"is_img": False, "img": None, "bold": False, "text": "暂无解析。"}], [], "暂无解析。"

    from docx.shared import Mm
    from PIL import Image

    mgr = img_mgr or image_manager
    analysis_segments: list[dict[str, Any]] = []
    analysis_images: list[InlineImage] = []
    text_pieces: list[str] = []
    last_idx = 0

    for match in IMG_TAG_PATTERN.finditer(exp_html):
        # 1. 前置文字片段处理
        text_chunk = exp_html[last_idx:match.start()]
        cleaned = clean_html_text_only(text_chunk)
        if cleaned:
            analysis_segments.append({"is_img": False, "img": None, "bold": False, "text": cleaned})
            text_pieces.append(cleaned)

        # 2. 图片属性分析与分流
        tag = match.group(0)
        src = match.group("src").strip()

        # 过滤已知符号图片（已在 clean_html_text_only 中转为字符）
        if any(h in src for h in KNOWN_SYMBOL_HASHES) or any(k in src.lower() for k in ["arrow", "rightarrow", "dash"]):
            last_idx = match.end()
            continue

        is_formula = 'flag="tex"' in tag or "flag='tex'" in tag or '/accessories/formulas' in src or '/formulas' in src

        local_path = mgr.get_local_path(src)
        if local_path and local_path.exists():
            try:
                with Image.open(local_path) as im:
                    w_px, h_px = im.size
                if is_formula or (0 < h_px <= 90 and 0 < w_px <= 550):
                    # 行内公式图片：自适应计算行内高度 (4.8mm ~ 7.5mm)
                    if h_px <= 45:
                        h_mm = 4.8
                    elif h_px <= 70:
                        h_mm = 6.2
                    else:
                        h_mm = 7.5

                    # 避免过宽超出可排版宽度
                    aspect = w_px / max(h_px, 1)
                    if h_mm * aspect > 95.0:
                        h_mm = 95.0 / aspect

                    inline_formula = InlineImage(doc, str(local_path), height=Mm(h_mm))
                    analysis_segments.append({"is_img": True, "img": inline_formula, "bold": False, "text": ""})
                else:
                    # 块级大配图：独占段落居中
                    block_img = mgr.create_inline_image(doc, src, max_width_mm=max_width_mm)
                    if block_img:
                        analysis_images.append(block_img)
            except Exception as e:
                logger.warning(f"解析图片处理异常: {src}, {e}")

        last_idx = match.end()

    # 3. 处理末尾剩余文字
    remaining_text = exp_html[last_idx:]
    cleaned_rem = clean_html_text_only(remaining_text)
    if cleaned_rem:
        analysis_segments.append({"is_img": False, "img": None, "bold": False, "text": cleaned_rem})
        text_pieces.append(cleaned_rem)

    full_clean_text = "".join(text_pieces).strip() or clean_html_text_only(exp_html) or "暂无解析。"

    # 若无任何有效片段，兜底填充
    if not analysis_segments:
        analysis_segments.append({"is_img": False, "img": None, "bold": False, "text": full_clean_text})

    return analysis_segments, analysis_images, full_clean_text


def parse_explanation_and_images(
    exp_html: str | None,
    doc: DocxTemplate,
    img_mgr: ImageManager | None = None,
    max_width_mm: float = 110.0,
) -> tuple[str, list[InlineImage]]:
    """
    解析题目解析（向前兼容接口）：
    返回 (纯文本解析, 解析配图 InlineImage 列表)
    """
    _, exp_images, clean_exp = parse_analysis_structure(exp_html, doc, img_mgr, max_width_mm)
    return clean_exp, exp_images
