#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公开免登录试卷重排接口数据载荷定义与转换器
负责将前端插件捕获的 UnifiedPaper 归一化清洗并映射为后端标准 RenderDocumentPayload
"""

import re
from typing import Any, Literal
from pydantic import BaseModel, Field

from backend.common.schema import SchemaBase
from backend.plugin.render_book.schema.payload import (
    RenderBookMeta,
    RenderDocumentPayload,
    RenderMaterialPayload,
    RenderPaperPayload,
    RenderPlanPayload,
    RenderQuestionOptionPayload,
    RenderQuestionPayload,
    RenderSectionPayload,
)
from backend.plugin.render_book.schema.render import (
    RenderOptions,
    RenderOutputTargets,
)


class UnifiedQuestionInput(BaseModel):
    id: str | int | None = None
    question_id: int | None = None
    order_num: int | None = None
    type: str | None = 'single'
    type_label: str | None = '单选题'
    stem: str = Field(..., description='题干内容，支持 HTML 或纯文本')
    options: list[Any] | None = Field(default=None, description='选项列表')
    answer: str | None = Field(default=None, description='参考答案')
    analysis: str | None = Field(default=None, description='试题解析')
    material: str | None = Field(default=None, description='长篇材料或背景资料')
    source: str | None = Field(default=None, description='试题来源')
    knowledge_points: list[str] | None = Field(default=None, description='核心考点微标签')
    tags: list[str] | None = Field(default=None, description='真题或分类标签')


class UnifiedSectionInput(BaseModel):
    name: str = Field(..., description='模块名称，如常识判断、言语理解与表达')
    description: str | None = Field(default=None, description='模块指引说明')
    questions: list[UnifiedQuestionInput] = Field(default_factory=list, description='试题列表')


class UnifiedPaperInput(BaseModel):
    title: str = Field(..., description='试卷全称')
    source_platform: str = Field(default='fenbi', description='来源题库平台')
    total_questions: int = Field(default=0, description='试卷题目总数')
    sections: list[UnifiedSectionInput] = Field(default_factory=list, description='大题模块列表')
    metadata: dict[str, Any] | None = Field(default=None, description='附加元数据')


class ReformatOptionsInput(BaseModel):
    include_answer: bool = Field(default=False, description='是否附带参考答案与解析')
    answer_placement: Literal['merged', 'separate', 'none'] = Field(
        default='merged',
        description='答案排布方式: merged=合在一个本子卷末, separate=分为独立PDF/分册, none=不含答案',
    )
    output_format: Literal['pdf', 'docx'] = Field(default='pdf', description='导出文件格式')


class PublicReformatRequest(BaseModel):
    paper: UnifiedPaperInput = Field(..., description='归一化试卷数据')
    options: ReformatOptionsInput = Field(default_factory=ReformatOptionsInput, description='排版设置')
    target: Literal['computer_download', 'mobile_sync'] = Field(
        default='computer_download', description='交付目标'
    )


class PublicReformatResponseData(SchemaBase):
    job_id: str = Field(description='排版任务唯一标识')
    file_name: str = Field(description='生成文件名称')
    download_url: str | None = Field(default=None, description='下载相对路径')
    output_format: str = Field(description='输出格式')
    remaining_quota: int = Field(description='今日剩余免登录可用额度')
    qr_code_url: str | None = Field(default=None, description='手机扫码同步/快速打印码链接')
    total_questions: int = Field(default=0, description='实际排版题量')
    extra_files: list[dict[str, Any]] | None = Field(default=None, description='分册文件列表，如答案解析卷')


OPTION_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']


def convert_unified_paper_to_document_payload(
    req: PublicReformatRequest,
) -> RenderDocumentPayload:
    """
    将前端插件提交的 PublicReformatRequest 转换为后端核心排版引擎可识别的 RenderDocumentPayload
    """
    paper = req.paper
    options = req.options

    # 1. 抽取与规整长篇资料/材料（材料去重与 ID 建立）
    material_cache: dict[str, int] = {}
    materials_list: list[RenderMaterialPayload] = []
    material_counter = 1000

    sections_payload: list[RenderSectionPayload] = []
    global_q_index = 1

    for s_idx, sec in enumerate(paper.sections, start=1):
        q_payloads: list[RenderQuestionPayload] = []

        for q in sec.questions:
            q_num = q.order_num if (q.order_num is not None and q.order_num > 0) else global_q_index
            global_q_index = max(global_q_index + 1, q_num + 1)

            # 材料绑定与去重
            mat_ids: list[int] = []
            if q.material and q.material.strip():
                mat_text = q.material.strip()
                if mat_text not in material_cache:
                    material_counter += 1
                    material_cache[mat_text] = material_counter
                    materials_list.append(
                        RenderMaterialPayload(
                            id=material_counter,
                            title=None,
                            content_text=mat_text,
                        )
                    )
                mat_ids.append(material_cache[mat_text])

            # 选项规范化解析
            parsed_options: list[RenderQuestionOptionPayload] = []
            if q.options:
                for opt_idx, opt_raw in enumerate(q.options):
                    default_key = OPTION_LETTERS[opt_idx] if opt_idx < len(OPTION_LETTERS) else str(opt_idx + 1)
                    if isinstance(opt_raw, dict):
                        key = str(opt_raw.get('key') or default_key).strip().upper()
                        text = str(opt_raw.get('value') or opt_raw.get('text') or opt_raw.get('content') or '').strip()
                    else:
                        str_val = str(opt_raw).strip()
                        # 增强匹配行首 "A." "A、" "A " 以及紧贴的 "B85-87千克"
                        match = re.match(r'^([A-Ha-h])(?:[\.、．\:\：\s]+|(?![\da-zA-Z]))\s*(.*)$', str_val)
                        if match:
                            key = match.group(1).upper()
                            text = match.group(2).strip()
                        else:
                            key = default_key
                            text = str_val

                    # 二次清洗文本中的残留选项字母
                    text = re.sub(r'^[A-Ha-h][\.\、\s]+', '', text).strip()

                    parsed_options.append(
                        RenderQuestionOptionPayload(
                            key=key,
                            content_text=text,
                        )
                    )

            # 题干防混杂清洗：若题干末尾混入了选项容器代码，将其切除
            clean_stem = q.stem or ''
            for opt_tag in ['<ul class="options', '<div class="options', '<div class="option-item', '<ol class="options']:
                if opt_tag in clean_stem:
                    clean_stem = clean_stem.split(opt_tag)[0].strip()

            q_payload = RenderQuestionPayload(
                number=q_num,
                question_id=q.question_id or q_num,
                type=q.type or 'single',
                type_label=q.type_label or '单选题',
                stem_text=clean_stem,
                options=parsed_options,
                answer_text=q.answer or '',
                analysis_text=q.analysis or '',
                source_text=q.source or '',
                material_ids=mat_ids,
                knowledge_points=q.knowledge_points or [],
                tags=q.tags or [],
            )
            q_payloads.append(q_payload)

        sections_payload.append(
            RenderSectionPayload(
                key=f'sec_{s_idx}',
                title=sec.name or f'第{s_idx}部分',
                questions=q_payloads,
            )
        )

    # 2.5 执行跨模块/章节去重与来源标签公因式智能合并
    from backend.plugin.render_book.service.dedup_service import deduplicate_and_merge_sections
    sections_payload, _ = deduplicate_and_merge_sections(sections_payload)

    actual_total_questions = sum(len(s.questions) for s in sections_payload)
    paper_title = paper.title.strip() if paper.title else '国家公务员录用考试行政职业能力测验'

    return RenderDocumentPayload(
        template_key='gongkao_xingce',
        render_plan=RenderPlanPayload(
            book_kind='exam',
            content_mode='questions_with_answers' if options.include_answer else 'questions_only',
            answer_layout='appendix',
            delivery_mode='single_pdf',
            solution_mode='appendix' if options.include_answer else 'none',
            output_targets=RenderOutputTargets(
                question_pdf=True,
                solution_pdf=options.include_answer,
            ),
            render_variants=['questions_only'],
        ),
        book=RenderBookMeta(
            title=paper_title,
            subtitle='行政职业能力测验',
            meta_lines=[
                f'总题量：{actual_total_questions} 题',
                '满分：100 分',
                '考试时限：120 分钟',
            ],
        ),
        options=RenderOptions(
            include_answer=options.include_answer,
            include_analysis=options.include_answer,
            layout_mode='standard',
            theme='blue',
        ),
        paper=RenderPaperPayload(
            question_count=actual_total_questions,
            material_count=len(materials_list),
            sections=sections_payload,
            materials=materials_list,
        ),
        metadata={
            'source': 'public_extension',
            'source_platform': paper.source_platform,
            'export_target': req.target,
            'output_format': options.output_format,
            'answer_placement': options.answer_placement,
            **(paper.metadata or {}),
        },
    )
