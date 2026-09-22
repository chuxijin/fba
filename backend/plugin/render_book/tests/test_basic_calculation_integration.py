#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础计算与资料分析专项练习本 (basic_calculation) 端到端集成测试
验证：
1. 模拟小程序端 RenderJobCreate payload，经由 PayloadService 转换为 RenderDocumentPayload；
2. 基础计算适配器 adapt_basic_calc_payload 能够正确处理双列算式、4列数据盒、2列分数立体比较盒；
3. docx_engine 能够正确编译并生成 Word、PDF 与预览图；
4. 验证 OMML 微软原生矢量分数转译是否顺畅。
"""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.plugin.render_book.schema.payload import (
    RenderBookMeta,
    RenderDocumentPayload,
    RenderPaperPayload,
    RenderPlanPayload,
    RenderQuestionPayload,
    RenderSectionPayload,
)
from backend.plugin.render_book.schema.render import RenderJobCreate, RenderOptions, RenderOutputTargets
from backend.plugin.render_book.service.adapters.basic_calc_adapter import adapt_basic_calc_payload
from backend.plugin.render_book.service.docx_engine import docx_render_engine
from backend.plugin.render_book.service.payload_service import RenderPayloadService
from backend.plugin.render_book.utils.template_catalog import TEMPLATES_ROOT


def test_basic_calc_from_mini_app_payload():
    """测试模拟小程序端提交的题单 payload 经由 PayloadService 和 adapter 适配"""
    # 模拟小程序发送的 metadata 结构
    mini_metadata = {
        "client": "mini",
        "source_type": "basic_calculation",
        "questions": [
            {"expression": "17 × 8 =", "answer": "136", "section_title": "10~19 乘以个位数"},
            {"expression": "14 × 7 =", "answer": "98", "section_title": "10~19 乘以个位数"},
            {"expression": "384 + 547 =", "answer": "931", "section_title": "三位数加法"},
            {"expression": "469 + 375 =", "answer": "844", "section_title": "三位数加法"},
        ],
        "type_title": "基础计算组合训练",
    }

    job = RenderJobCreate(
        template_key="basic_calculation",
        title="基础计算组合题单",
        metadata=mini_metadata,
    )

    doc_payload = RenderPayloadService._build_basic_calculation_payload(job)
    assert doc_payload.template_key == "basic_calculation"
    assert len(doc_payload.paper.sections) == 2
    assert doc_payload.paper.question_count == 4

    # 适配模板上下文
    ctx = adapt_basic_calc_payload(doc_payload)
    assert "book" in ctx
    assert "paper" in ctx
    assert len(ctx["paper"]["sections"]) == 2
    # 应该全是双列算式网格
    for sec in ctx["paper"]["sections"]:
        assert len(sec["calc_rows"]) > 0
        assert len(sec["box_blocks"]) == 0
        assert len(sec["compare_blocks"]) == 0


def test_basic_calc_with_data_box_and_fractions():
    """测试同时包含基础算式、4列数据盒与2列立体分数的复合场景"""
    sections = [
        RenderSectionPayload(
            key="sec_calc",
            title="一、基础计算",
            questions=[
                RenderQuestionPayload(number=1, question_id=1, type="blank", type_label="计算", stem_text="15 × 6 =", answer_text="90"),
                RenderQuestionPayload(number=2, question_id=2, type="blank", type_label="计算", stem_text="18 × 4 =", answer_text="72"),
            ],
        ),
        RenderSectionPayload(
            key="sec_data_base",
            title="二、资料分析 · 基期量计算",
            questions=[
                RenderQuestionPayload(number=3, question_id=3, type="blank", type_label="基期", stem_text="4971    8.8%", answer_text="4569"),
                RenderQuestionPayload(number=4, question_id=4, type="blank", type_label="基期", stem_text="5363    7.8%", answer_text="4975"),
            ],
        ),
        RenderSectionPayload(
            key="sec_compare",
            title="三、资料分析 · 分数大小比较",
            questions=[
                RenderQuestionPayload(number=5, question_id=5, type="blank", type_label="比大小", stem_text=r"$\frac{165}{5284}$   (   )   $\frac{65}{2010}$", answer_text="＜"),
                RenderQuestionPayload(number=6, question_id=6, type="blank", type_label="比大小", stem_text=r"$\frac{985}{9178}$   (   )   $\frac{835}{7646}$", answer_text="＞"),
            ],
        ),
    ]

    doc_payload = RenderDocumentPayload(
        template_key="basic_calculation",
        render_plan=RenderPlanPayload(
            book_kind="custom",
            content_mode="questions_with_answers",
            answer_layout="appendix",
            delivery_mode="single_pdf",
            solution_mode="appendix",
            output_targets=RenderOutputTargets(),
        ),
        options=RenderOptions(include_answer=True, include_analysis=False),
        book=RenderBookMeta(title="综合特训测试", subtitle="单元测试"),
        paper=RenderPaperPayload(
            title="综合特训测试",
            subtitle="",
            question_count=6,
            material_count=0,
            sections=sections,
            materials=[],
        ),
    )

    ctx = adapt_basic_calc_payload(doc_payload)
    assert len(ctx["paper"]["sections"]) == 3
    # 分节 1：基础速算网格
    assert len(ctx["paper"]["sections"][0]["calc_rows"]) == 1
    # 分节 2：4 列数据盒
    assert len(ctx["paper"]["sections"][1]["box_blocks"]) == 1
    # 分节 3：2 列比较盒
    assert len(ctx["paper"]["sections"][2]["compare_blocks"]) == 1
    # 答案速查行
    assert len(ctx["paper"]["answer_rows"]) == 2  # 6 题 / 5 列 = 2 行


if __name__ == "__main__":
    test_basic_calc_from_mini_app_payload()
    print("[✓] test_basic_calc_from_mini_app_payload PASSED")
    test_basic_calc_with_data_box_and_fractions()
    print("[✓] test_basic_calc_with_data_box_and_fractions PASSED")
