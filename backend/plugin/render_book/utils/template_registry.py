#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.render_book.schema.render import (
    RenderFieldChoice,
    RenderFieldSpec,
    RenderOptions,
    RenderTemplateDetail,
)
from backend.plugin.render_book.utils.template_catalog import get_latest_template_manifests


def get_template_registry() -> dict[str, RenderTemplateDetail]:
    base_option_fields = [
        RenderFieldSpec(key='include_answer', label='显示答案', field_type='boolean', default=False),
        RenderFieldSpec(key='include_analysis', label='显示解析', field_type='boolean', default=False),
        RenderFieldSpec(
            key='layout_mode',
            label='版式',
            field_type='single_select',
            default='standard',
            choices=[
                RenderFieldChoice(value='compact', label='紧凑'),
                RenderFieldChoice(value='standard', label='标准'),
                RenderFieldChoice(value='loose', label='宽松'),
                RenderFieldChoice(value='single', label='单题版'),
                RenderFieldChoice(value='pad_landscape', label='Pad 横版'),
                RenderFieldChoice(value='pad_portrait', label='Pad 竖版'),
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
                RenderFieldChoice(value='teal', label='青色'),
                RenderFieldChoice(value='crimson', label='红色'),
                RenderFieldChoice(value='indigo', label='靛蓝'),
                RenderFieldChoice(value='amber', label='琥珀'),
            ],
        ),
        RenderFieldSpec(key='dark_mode', label='暗色模式', field_type='boolean', default=False),
        RenderFieldSpec(key='show_source', label='显示题目来源', field_type='boolean', default=True),
    ]
    common_source_fields = [
        RenderFieldSpec(key='bank_id', label='题库 ID', field_type='integer', description='按题库上下文取题'),
        RenderFieldSpec(key='chapter_id', label='章节 ID', field_type='integer', description='按章节上下文取题'),
        RenderFieldSpec(key='cat_id', label='分类 ID', field_type='integer', description='按试卷/合集分类筛题'),
        RenderFieldSpec(key='region', label='地区关键字', field_type='string', description='按试卷名称/编码/描述匹配'),
        RenderFieldSpec(key='year_start', label='起始年份', field_type='integer', description='按题目创建年过滤'),
        RenderFieldSpec(key='year_end', label='结束年份', field_type='integer', description='按题目创建年过滤'),
        RenderFieldSpec(
            key='question_ids', label='题目 ID 列表', field_type='string', description='逗号分隔，如 101,102,103'
        ),
        RenderFieldSpec(
            key='question_types',
            label='题型',
            field_type='multi_select',
            choices=[
                RenderFieldChoice(value='single', label='单选题'),
                RenderFieldChoice(value='multiple', label='多选题'),
                RenderFieldChoice(value='judgement', label='判断题'),
                RenderFieldChoice(value='fill', label='填空题'),
                RenderFieldChoice(value='shortAnswer', label='简答题'),
            ],
        ),
        RenderFieldSpec(
            key='difficulties',
            label='难度',
            field_type='multi_select',
            choices=[
                RenderFieldChoice(value='easy', label='简单'),
                RenderFieldChoice(value='medium', label='中等'),
                RenderFieldChoice(value='hard', label='困难'),
            ],
        ),
        RenderFieldSpec(key='knowledge_points', label='考点', field_type='multi_select', description='按考点名称过滤'),
        RenderFieldSpec(key='stem_keyword', label='题干关键字', field_type='string', description='按题干文本模糊搜索'),
        RenderFieldSpec(
            key='option_keyword', label='选项关键字', field_type='string', description='按选项文本模糊搜索'
        ),
        RenderFieldSpec(
            key='analysis_keyword', label='解析关键字', field_type='string', description='按解析文本模糊搜索'
        ),
        RenderFieldSpec(key='question_count', label='题量', field_type='integer', required=False, default=100),
    ]

    registry = {
        'exam_paper': RenderTemplateDetail(
            key='exam_paper',
            name='真题套卷',
            description='按年份、地区、卷型生成完整真题套卷。',
            scene='套卷模拟',
            subject='真题',
            estimated_latency='slow',
            filter_fields=[
                RenderFieldSpec(
                    key='bank_id', label='试卷题库 ID', field_type='integer', description='优先指定某一套卷题库'
                ),
                RenderFieldSpec(
                    key='chapter_id', label='章节 ID', field_type='integer', description='按指定章节裁剪套卷'
                ),
                RenderFieldSpec(key='cat_id', label='分类 ID', field_type='integer', description='按试卷分类筛题'),
                RenderFieldSpec(
                    key='region', label='地区关键字', field_type='string', description='按试卷名称/编码/描述匹配'
                ),
                RenderFieldSpec(
                    key='year_start', label='起始年份', field_type='integer', description='按题目创建年过滤'
                ),
                RenderFieldSpec(key='year_end', label='结束年份', field_type='integer', description='按题目创建年过滤'),
                RenderFieldSpec(
                    key='question_ids', label='题目 ID 列表', field_type='string', description='直接锁定套卷题目'
                ),
                RenderFieldSpec(
                    key='question_types',
                    label='题型',
                    field_type='multi_select',
                    choices=[
                        RenderFieldChoice(value='single', label='单选题'),
                        RenderFieldChoice(value='multiple', label='多选题'),
                        RenderFieldChoice(value='judgement', label='判断题'),
                        RenderFieldChoice(value='fill', label='填空题'),
                        RenderFieldChoice(value='shortAnswer', label='简答题'),
                    ],
                ),
                RenderFieldSpec(
                    key='difficulties',
                    label='难度',
                    field_type='multi_select',
                    choices=[
                        RenderFieldChoice(value='easy', label='简单'),
                        RenderFieldChoice(value='medium', label='中等'),
                        RenderFieldChoice(value='hard', label='困难'),
                    ],
                ),
                RenderFieldSpec(
                    key='knowledge_points', label='考点', field_type='multi_select', description='按考点名称过滤'
                ),
                RenderFieldSpec(
                    key='stem_keyword', label='题干关键字', field_type='string', description='按题干文本模糊搜索'
                ),
                RenderFieldSpec(
                    key='option_keyword', label='选项关键字', field_type='string', description='按选项文本模糊搜索'
                ),
                RenderFieldSpec(
                    key='analysis_keyword', label='解析关键字', field_type='string', description='按解析文本模糊搜索'
                ),
                RenderFieldSpec(key='question_count', label='题量', field_type='integer', default=120),
            ],
            option_fields=base_option_fields,
            default_options=RenderOptions(theme='blue'),
            notes=['适合考前整卷演练。', '当前第一版优先按真实题库 ID 或题目 ID 列表生成。'],
        ),
        'practice': RenderTemplateDetail(
            key='practice',
            name='刷题练习本',
            description='按题目、题型、难度、考点等条件自由组合生成练习本。',
            scene='专项训练',
            subject='练习',
            estimated_latency='medium',
            filter_fields=common_source_fields,
            option_fields=base_option_fields,
            default_options=RenderOptions(theme='green'),
            notes=['适合运营、教研或用户按任意条件生成个性化练习本。'],
        ),
        'wrong_question': RenderTemplateDetail(
            key='wrong_question',
            name='错题重刷',
            description='根据用户错题记录生成个性化错题本。',
            scene='个性化训练',
            subject='错题',
            estimated_latency='medium',
            filter_fields=[
                RenderFieldSpec(key='bank_id', label='题库 ID', field_type='integer', description='只取某题库内的错题'),
                RenderFieldSpec(
                    key='chapter_id', label='章节 ID', field_type='integer', description='只取某章节内的错题'
                ),
                RenderFieldSpec(key='cat_id', label='分类 ID', field_type='integer', description='按试卷/合集分类筛题'),
                RenderFieldSpec(
                    key='region', label='地区关键字', field_type='string', description='按试卷名称/编码/描述匹配'
                ),
                RenderFieldSpec(
                    key='year_start', label='起始年份', field_type='integer', description='按题目创建年过滤'
                ),
                RenderFieldSpec(key='year_end', label='结束年份', field_type='integer', description='按题目创建年过滤'),
                RenderFieldSpec(
                    key='knowledge_points', label='考点', field_type='multi_select', description='按考点名称筛选'
                ),
                RenderFieldSpec(
                    key='question_types',
                    label='题型',
                    field_type='multi_select',
                    choices=[
                        RenderFieldChoice(value='single', label='单选题'),
                        RenderFieldChoice(value='multiple', label='多选题'),
                        RenderFieldChoice(value='judgement', label='判断题'),
                        RenderFieldChoice(value='fill', label='填空题'),
                        RenderFieldChoice(value='shortAnswer', label='简答题'),
                    ],
                ),
                RenderFieldSpec(
                    key='difficulties',
                    label='难度',
                    field_type='multi_select',
                    choices=[
                        RenderFieldChoice(value='easy', label='简单'),
                        RenderFieldChoice(value='medium', label='中等'),
                        RenderFieldChoice(value='hard', label='困难'),
                    ],
                ),
                RenderFieldSpec(
                    key='stem_keyword', label='题干关键字', field_type='string', description='按题干文本模糊搜索'
                ),
                RenderFieldSpec(
                    key='option_keyword', label='选项关键字', field_type='string', description='按选项文本模糊搜索'
                ),
                RenderFieldSpec(
                    key='analysis_keyword', label='解析关键字', field_type='string', description='按解析文本模糊搜索'
                ),
                RenderFieldSpec(key='question_count', label='题量', field_type='integer', default=50),
                RenderFieldSpec(
                    key='wrong_only_recent_days',
                    label='最近天数',
                    field_type='integer',
                    description='限制最近多少天的错题',
                ),
            ],
            option_fields=base_option_fields,
            default_options=RenderOptions(include_answer=True, theme='orange'),
            notes=['需要传入 metadata.user_id 作为用户错题来源。'],
        ),
        'basic_calculation': RenderTemplateDetail(
            key='basic_calculation',
            name='基础计算练习',
            description='根据即时生成的口算、估算、除法等训练题生成打印题单。',
            scene='能力训练',
            subject='基础计算',
            estimated_latency='fast',
            filter_fields=[
                RenderFieldSpec(key='question_count', label='题量', field_type='integer', default=20),
                RenderFieldSpec(
                    key='type_title', label='训练类型', field_type='string', description='由小程序写入 metadata'
                ),
            ],
            option_fields=base_option_fields,
            default_options=RenderOptions(theme='amber', show_source=False),
            notes=['题目由 metadata.questions 直传，不依赖题库题目表。'],
        ),
        'hanyu': RenderTemplateDetail(
            key='hanyu',
            name='汉语词汇手册',
            description='汉语词汇积累与复习手册，支持词语卡片式排版，含拼音、释义、例句、近反义词等。',
            scene='能力训练',
            subject='汉语',
            estimated_latency='medium',
            filter_fields=[
                RenderFieldSpec(
                    key='hanyu_ids', label='词汇 ID 列表', field_type='string', description='逗号分隔，如 101,102,103'
                ),
                RenderFieldSpec(
                    key='hanyu_type',
                    label='词汇类型',
                    field_type='single_select',
                    default='all',
                    choices=[
                        RenderFieldChoice(value='all', label='全部词汇'),
                        RenderFieldChoice(value='idiom', label='成语'),
                        RenderFieldChoice(value='word', label='普通词语'),
                    ],
                ),
            ],
            option_fields=base_option_fields,
            default_options=RenderOptions(theme='teal'),
            notes=['包含成语、词语的拼音、基本释义、例句、出处与近反义词。'],
        ),
    }

    manifests = get_latest_template_manifests()
    for template_key, manifest in manifests.items():
        template = registry.get(template_key)
        manifest_values = {
            'key': manifest.key,
            'version': manifest.version,
            'digest': manifest.digest,
            'name': manifest.name,
            'description': manifest.description,
            'default_variant': manifest.default_variant,
            'supported_variants': manifest.supported_variants,
        }
        if template is None:
            registry[template_key] = RenderTemplateDetail(
                **manifest_values,
                scene='通用模板',
            )
            continue
        registry[template_key] = template.model_copy(update=manifest_values)

    return {template_key: registry[template_key] for template_key in manifests}
