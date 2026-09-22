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


def clean_html_text_only(text: str | None) -> str:
    """清理 HTML 标签，返回纯净文本（剥离图片标签及格式噪音）"""
    if not text:
        return ""
    s = re.sub(r'<\s*br\s*/?>', '\n', text, flags=re.IGNORECASE)
    s = re.sub(r'</\s*p\s*>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'</\s*div\s*>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'<[^>]+>', '', s)
    s = s.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    lines = [line.strip() for line in s.split('\n')]
    return '\n'.join([line for line in lines if line])


def clean_opt_text_only(text: str | None, key: str) -> str:
    """清理选项文本并去除冗余的选项编号前缀（如 A.、A、A:）"""
    cleaned = clean_html_text_only(text)
    return re.sub(rf'^{re.escape(key)}[\.\、\s\:\：]+', '', cleaned, flags=re.IGNORECASE).strip()


def extract_image_urls(html_text: str | None) -> list[str]:
    """提取 HTML 中的所有图片 URL 列表"""
    if not html_text:
        return []
    return [m.group("src").strip() for m in IMG_TAG_PATTERN.finditer(html_text) if m.group("src").strip()]


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


def parse_stem_and_images(
    stem_html: str | None,
    doc: DocxTemplate,
    img_mgr: ImageManager | None = None,
    max_width_mm: float = 120.0,
) -> tuple[str, list[InlineImage]]:
    """
    解析题干：
    返回 (纯文本题干, 题干配图 InlineImage 列表)
    """
    if not stem_html:
        return "", []

    mgr = img_mgr or image_manager
    clean_stem = clean_html_text_only(stem_html)
    img_urls = extract_image_urls(stem_html)

    stem_images: list[InlineImage] = []
    for url in img_urls:
        inline_img = mgr.create_inline_image(doc, url, max_width_mm=max_width_mm)
        if inline_img:
            stem_images.append(inline_img)

    return clean_stem, stem_images


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


def parse_explanation_and_images(
    exp_html: str | None,
    doc: DocxTemplate,
    img_mgr: ImageManager | None = None,
    max_width_mm: float = 110.0,
) -> tuple[str, list[InlineImage]]:
    """
    解析题目解析：
    返回 (纯文本解析, 解析配图 InlineImage 列表)
    """
    if not exp_html:
        return "暂无解析。", []

    mgr = img_mgr or image_manager
    clean_exp = clean_html_text_only(exp_html)
    img_urls = extract_image_urls(exp_html)

    exp_images: list[InlineImage] = []
    for url in img_urls:
        inline_img = mgr.create_inline_image(doc, url, max_width_mm=max_width_mm)
        if inline_img:
            exp_images.append(inline_img)

    return clean_exp or "暂无解析。", exp_images
