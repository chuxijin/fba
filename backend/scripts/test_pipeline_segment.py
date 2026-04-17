#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试正则分段引擎对考研政治真题 PDF 的效果"""
import sys
import os

# 添加项目根目录到 sys.path
sys.path.insert(0, r'd:\100_Work\101_Program\Proj\fba')

PDF_PATH = r'E:\600-Download_File\602_浏览器文件下载位置\2025考研政治真题.pdf'


def extract_text_from_pdf(pdf_path: str) -> str:
    """用 pymupdf 提取 PDF 文本"""
    import pymupdf
    doc = pymupdf.open(pdf_path)
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return '\n'.join(text_parts)


def test_segmentation():
    """测试正则分段"""
    from backend.app.question_bank.service.pipeline_service import pipeline_service

    print(f'📄 PDF: {PDF_PATH}')
    print(f'📏 文件大小: {os.path.getsize(PDF_PATH):,} bytes')
    print()

    # 1. 提取文本
    print('--- 阶段 1: 提取 PDF 文本 ---')
    text = extract_text_from_pdf(PDF_PATH)
    print(f'总字符数: {len(text)}')
    print(f'总行数: {text.count(chr(10)) + 1}')
    print()

    # 打印前 500 字符看看文本质量
    print('--- 文本前 500 字符 ---')
    print(text[:500])
    print('...')
    print()

    # 2. 正则分段
    print('--- 阶段 2: 正则分段 ---')
    segments = pipeline_service.segment_markdown(text)
    print(f'分段数量: {len(segments)}')
    print()

    # 3. 打印每个分段的预览
    for i, seg in enumerate(segments):
        preview = seg[:120].replace('\n', ' ↵ ')
        if len(seg) > 120:
            preview += '...'
        print(f'  [{i + 1:3d}] ({len(seg):5d} 字) {preview}')

    print()
    print(f'✅ 分段测试完成，共 {len(segments)} 段')

    # 4. 也测试 preview_segments
    print()
    print('--- 阶段 3: 预览结构 ---')
    previews = pipeline_service.preview_segments(text)
    print(f'预览总数: {len(previews)}')
    for p in previews[:5]:
        print(f'  [{p["index"]}] len={p["length"]} | {p["preview"][:80]}')
    if len(previews) > 5:
        print(f'  ... 还有 {len(previews) - 5} 个')


if __name__ == '__main__':
    test_segmentation()
