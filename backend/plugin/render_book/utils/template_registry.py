#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.render_book.schema.render import RenderFieldChoice, RenderFieldSpec, RenderOptions, RenderTemplateDetail


def get_template_registry() -> dict[str, RenderTemplateDetail]:
    base_option_fields = [
        RenderFieldSpec(key='include_answer', label='显示答案', field_type='boolean', default=False),
        RenderFieldSpec(key='include_analysis', label='显示解析', field_type='boolean', default=False),
        RenderFieldSpec(
            key='density',
            label='排版密度',
            field_type='single_select',
            default='standard',
            choices=[
                RenderFieldChoice(value='compact', label='紧凑'),
                RenderFieldChoice(value='standard', label='标准'),
                RenderFieldChoice(value='loose', label='宽松'),
            ],
        ),
        RenderFieldSpec(
            key='theme',
            label='主题色',
            field_type='single_select',
            default='blue',
            choices=[
                RenderFieldChoice(value='blue', label='蓝色'),
                RenderFieldChoice(value='green', label='绿色'),
                RenderFieldChoice(value='orange', label='橙色'),
                RenderFieldChoice(value='purple', label='紫色'),
            ],
        ),
        RenderFieldSpec(key='show_source', label='显示题目来源', field_type='boolean', default=True),
    ]

    return {
        'language_core': RenderTemplateDetail(
            key='language_core',
            name='言语刷题本',
            description='按题型和题量组合生成言语理解题本。',
            scene='专项训练',
            subject='言语',
            estimated_latency='fast',
            filter_fields=[
                RenderFieldSpec(key='question_types', label='题型', field_type='multi_select', description='如逻辑填空、片段阅读、语句表达'),
                RenderFieldSpec(key='years', label='年份', field_type='multi_select', description='题目来源年份'),
                RenderFieldSpec(key='question_count', label='题量', field_type='integer', required=False, default=100),
            ],
            option_fields=base_option_fields,
            default_options=RenderOptions(theme='blue'),
            notes=['适合生成日常专项训练题本。'],
        ),
        'quantitative_core': RenderTemplateDetail(
            key='quantitative_core',
            name='数量刷题本',
            description='按模块筛选数量关系题目并生成练习册。',
            scene='专项训练',
            subject='数量',
            estimated_latency='fast',
            filter_fields=[
                RenderFieldSpec(key='question_types', label='题型', field_type='multi_select', description='如数字推理、数学运算'),
                RenderFieldSpec(key='years', label='年份', field_type='multi_select'),
                RenderFieldSpec(key='question_count', label='题量', field_type='integer', default=80),
            ],
            option_fields=base_option_fields,
            default_options=RenderOptions(theme='green'),
            notes=['适合按模块反复刷题。'],
        ),
        'judgment_core': RenderTemplateDetail(
            key='judgment_core',
            name='判断刷题本',
            description='生成定义判断、类比推理、图形推理等判断推理题本。',
            scene='专项训练',
            subject='判断',
            estimated_latency='fast',
            filter_fields=[
                RenderFieldSpec(key='question_types', label='题型', field_type='multi_select'),
                RenderFieldSpec(key='years', label='年份', field_type='multi_select'),
                RenderFieldSpec(key='question_count', label='题量', field_type='integer', default=100),
            ],
            option_fields=base_option_fields,
            default_options=RenderOptions(theme='orange'),
            notes=['适合按知识点或题型拆分生成。'],
        ),
        'material_digest': RenderTemplateDetail(
            key='material_digest',
            name='资料刷题本',
            description='生成图表、文字、综合资料类练习内容。',
            scene='资料训练',
            subject='资料',
            estimated_latency='medium',
            filter_fields=[
                RenderFieldSpec(key='material_types', label='资料类型', field_type='multi_select', description='如文字资料、图形资料、表格资料'),
                RenderFieldSpec(key='years', label='年份', field_type='multi_select'),
                RenderFieldSpec(key='question_count', label='题量', field_type='integer', default=40),
            ],
            option_fields=base_option_fields,
            default_options=RenderOptions(theme='purple'),
            notes=['资料题通常每题块内容较长，预览耗时会略高。'],
        ),
        'exam_paper': RenderTemplateDetail(
            key='exam_paper',
            name='真题套卷',
            description='按年份、地区、卷型生成完整真题套卷。',
            scene='套卷模拟',
            subject='真题',
            estimated_latency='slow',
            filter_fields=[
                RenderFieldSpec(key='years', label='年份', field_type='multi_select', required=True),
                RenderFieldSpec(key='regions', label='地区', field_type='multi_select', description='如国考、省考、地市级'),
                RenderFieldSpec(key='paper_types', label='卷型', field_type='multi_select', description='如副省级、地市级、行政执法'),
            ],
            option_fields=base_option_fields,
            default_options=RenderOptions(theme='blue'),
            notes=['适合考前整卷演练。', '建议至少指定年份或卷型。'],
        ),
        'wrong_question': RenderTemplateDetail(
            key='wrong_question',
            name='错题重刷',
            description='根据用户错题记录生成个性化错题本。',
            scene='个性化训练',
            subject='错题',
            estimated_latency='medium',
            filter_fields=[
                RenderFieldSpec(key='subject_modules', label='模块', field_type='multi_select'),
                RenderFieldSpec(key='question_count', label='题量', field_type='integer', default=50),
                RenderFieldSpec(key='wrong_only_recent_days', label='最近天数', field_type='integer', description='限制最近多少天的错题'),
            ],
            option_fields=base_option_fields,
            default_options=RenderOptions(include_answer=True, theme='orange'),
            notes=['需要传入 metadata.user_id 作为用户错题来源。'],
        ),
    }
