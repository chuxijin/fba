# -*- coding: utf-8 -*-
"""
试卷排版题目自动去重与来源标签智能合并单元及端到端集成测试
测试重点：
1. 来源标签公因式提取合并器 (merge_source_labels)；
2. 题目指纹比对与跨卷去重 (deduplicate_and_merge_sections)；
3. GongkaoAdapter / DocxRenderEngine 实测渲染生成 Word/PDF 题本。
"""

import time
from pathlib import Path

import pytest

from backend.plugin.render_book.schema.payload import (
    RenderBookMeta,
    RenderDocumentPayload,
    RenderPaperPayload,
    RenderPlanPayload,
    RenderQuestionOptionPayload,
    RenderQuestionPayload,
    RenderSectionPayload,
)
from backend.plugin.render_book.schema.render import RenderOptions, RenderOutputTargets
from backend.plugin.render_book.service.adapters import adapt_gongkao_payload
from backend.plugin.render_book.service.dedup_service import (
    build_question_fingerprint,
    merge_source_labels,
    deduplicate_and_merge_sections,
)
from backend.plugin.render_book.service.docx_engine import docx_render_engine
from backend.plugin.render_book.utils.template_catalog import TEMPLATES_ROOT

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_merge_source_labels_rule_matrix():
    """测试各类公考真题来源标签提取公因式合并"""
    # 1. 26 国考地市 + 行政执法
    res1 = merge_source_labels([
        '2026年国家公务员录用考试《行测》（市地级）',
        '2026年国家公务员录用考试《行测》（行政执法）',
    ])
    assert res1 == '26国考·地市 & 行政执法'

    # 2. 26 国考三卷合一（副省 + 地市 + 行政执法）
    res2 = merge_source_labels([
        '2026国考副省级',
        '2026国考市地级',
        '2026国考行政执法',
    ])
    assert res2 == '26国考·副省 & 地市 & 行政执法'

    # 3. 省考多类别（江苏 A类 + B类）
    res3 = merge_source_labels([
        '2025年江苏公务员考试《行测》（A类）',
        '2025年江苏公务员考试《行测》（B类）',
    ])
    assert res3 == '25江苏·A类 & B类'

    # 4. 多省联考复用（湖北 + 重庆）
    res4 = merge_source_labels([
        '2023年0225湖北公务员考试《行测》',
        '2023年0225重庆公务员考试《行测》',
    ])
    assert res4 == '23联考·湖北 & 重庆'


def test_deduplicate_and_merge_pipeline():
    """测试跨卷题目自动去重、来源合并及题号平滑顺延全流程"""
    # 模拟言语理解真题（在 2026 国考地市 与 2026 国考行政执法 中重复出现）
    shared_stem = '<p>在漫长的历史进程中，中华民族创造了独树一帜的灿烂文化，也形成了独特的审美传统和价值追求。填入画横线部分最恰当的一项是：</p>'
    shared_opts = [
        RenderQuestionOptionPayload(key='A', content_text='休戚与共 守望相助'),
        RenderQuestionOptionPayload(key='B', content_text='源远流长 博大精深'),
        RenderQuestionOptionPayload(key='C', content_text='交相辉映 相辅相成'),
        RenderQuestionOptionPayload(key='D', content_text='纷繁复杂 蔚为大观'),
    ]

    sec_dishi = RenderSectionPayload(
        key='sec_ds',
        title='言语理解与表达（地市卷）',
        questions=[
            RenderQuestionPayload(
                number=1,
                question_id=101,
                type='single_choice',
                type_label='单选题',
                stem_text=shared_stem,
                options=shared_opts,
                source_label='2026年国家公务员录用考试《行测》（市地级）',
            ),
            RenderQuestionPayload(
                number=2,
                question_id=102,
                type='single_choice',
                type_label='单选题',
                stem_text='<p>地市卷独有题目：现代科技正以不可逆转之势塑造人类生活...</p>',
                options=[RenderQuestionOptionPayload(key='A', content_text='选项A')],
                source_label='2026年国家公务员录用考试《行测》（市地级）',
            ),
        ],
    )

    sec_xzzf = RenderSectionPayload(
        key='sec_zf',
        title='言语理解与表达（行政执法卷）',
        questions=[
            RenderQuestionPayload(
                number=1,
                question_id=201,
                type='single_choice',
                type_label='单选题',
                # 题干带有轻微排版空格，测试指纹容差清洗
                stem_text='<div>在漫长的历史进程中，中华民族创造了独树一帜的灿烂文化，也形成了独特的审美传统和价值追求。填入画横线部分最恰当的一项是：&nbsp;</div>',
                options=[
                    RenderQuestionOptionPayload(key='A', content_text='A. 休戚与共 守望相助'),
                    RenderQuestionOptionPayload(key='B', content_text='B. 源远流长 博大精深'),
                    RenderQuestionOptionPayload(key='C', content_text='C. 交相辉映 相辅相成'),
                    RenderQuestionOptionPayload(key='D', content_text='D. 纷繁复杂 蔚为大观'),
                ],
                source_label='2026年国家公务员录用考试《行测》（行政执法）',
            ),
            RenderQuestionPayload(
                number=2,
                question_id=202,
                type='single_choice',
                type_label='单选题',
                stem_text='<p>行政执法独有题目：执法办案必须严格遵守法定程序...</p>',
                options=[RenderQuestionOptionPayload(key='A', content_text='选项A')],
                source_label='2026年国家公务员录用考试《行测》（行政执法）',
            ),
        ],
    )

    # 1. 执行去重合并
    new_secs, dedup_count = deduplicate_and_merge_sections([sec_dishi, sec_xzzf])

    # 验证去重效果
    assert dedup_count == 1, '应精准识别并去除 1 道重复题目'
    total_qs = sum(len(s.questions) for s in new_secs)
    assert total_qs == 3, f'4道题去重后应为3道题，实际={total_qs}'

    first_q = new_secs[0].questions[0]
    print(f'[✓] 首题合并后的来源标签: {first_q.source_label}')
    assert first_q.source_label == '26国考·地市 & 行政执法'
    assert first_q.number == 1

    # 检查题号顺延
    all_numbers = [q.number for s in new_secs for q in s.questions]
    assert all_numbers == [1, 2, 3], f'题号必须严格重排顺延 [1, 2, 3]，实际={all_numbers}'

    # 2. 端到端适配与渲染 Word / PDF 考场试卷
    payload = RenderDocumentPayload(
        template_key='gongkao_xingce',
        render_plan=RenderPlanPayload(
            book_kind='exam',
            content_mode='questions_only',
            answer_layout='inline',
            delivery_mode='single_pdf',
            solution_mode='none',
            output_targets=RenderOutputTargets(question_pdf=True),
        ),
        book=RenderBookMeta(title='2026年国家公务员录用考试行测言语专项突破'),
        options=RenderOptions(),
        paper=RenderPaperPayload(
            question_count=total_qs,
            sections=new_secs,
        ),
    )

    template_file = TEMPLATES_ROOT / 'gongkao_xingce' / '1.0.0' / 'template.docx'
    ctx = adapt_gongkao_payload(payload, template_file=template_file)

    # 验证题干前缀是否包含来源标签
    parts = ctx['paper']['parts']
    first_stem_segments = parts[0]['questions'][0]['stem_segments']
    first_seg_text = first_stem_segments[0]['text']
    print(f'[✓] 试卷上下文首题段落前缀: {first_seg_text}')
    assert '【26国考·地市 & 行政执法】' in first_seg_text

    # 3. 调用 Word 引擎本地极速生成
    out_dir = PROJECT_ROOT / 'backend' / 'output' / 'exam_test' / 'dedup_test'
    out_dir.mkdir(parents=True, exist_ok=True)
    res = docx_render_engine.render_all(
        template_file=template_file,
        context=ctx,
        output_dir=out_dir,
        base_name=f'dedup_merged_test_{int(time.time())}',
        compile_pdf=True,
        max_previews=1,
    )
    docx_file = Path(res['docx'])
    pdf_file = Path(res['pdf'])
    assert docx_file.exists() and docx_file.stat().st_size > 5000
    assert pdf_file.exists() and pdf_file.stat().st_size > 10000
    print(f'[✓] Word 交付卷生成成功: {docx_file}')
    print(f'[✓] PDF 考场矢量卷生成成功: {pdf_file}')
