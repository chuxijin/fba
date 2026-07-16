#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Callable
from decimal import Decimal
from random import SystemRandom
from typing import Any

from backend.common.exception import errors

ChallengeGeneratedQuestion = dict[str, Any]
ChallengeGenerator = Callable[[str, dict[str, Any]], ChallengeGeneratedQuestion]

_random = SystemRandom()

DATA_ANALYSIS_CONCEPTS = [
    {
        'id': 'base_value',
        'name': '基期值',
        'definition': '作为比较基础的前一时期数值',
    },
    {
        'id': 'current_value',
        'name': '现期值',
        'definition': '当前统计时期的数值',
    },
    {
        'id': 'growth_amount',
        'name': '增长量',
        'definition': '现期值比基期值增加的数量',
    },
    {
        'id': 'change_amount',
        'name': '变化量',
        'definition': '两个时期数值相减得到的增减量',
    },
    {
        'id': 'change_rate',
        'name': '变化幅度',
        'definition': '变化量与比较基准的比值，表示相对变化程度',
    },
    {
        'id': 'growth_rate',
        'name': '增长率',
        'definition': '增长量与基期值的比值',
    },
    {
        'id': 'yoy',
        'name': '同比',
        'definition': '与上一年同期相比',
    },
    {
        'id': 'mom',
        'name': '环比',
        'definition': '与上一统计周期相比',
    },
]


def _build_single_choice_question(
    *,
    stem: str,
    values: list[Decimal],
    correct_value: Decimal,
    analysis: str,
    material: str | None,
    difficulty: Decimal,
    suffix: str = '',
) -> ChallengeGeneratedQuestion:
    """
    构建单选生成题

    :param stem: 题干
    :param values: 选项数值
    :param correct_value: 正确数值
    :param analysis: 解析
    :param material: 材料
    :param difficulty: 难度
    :param suffix: 选项后缀
    :return:
    """
    unique_values: list[Decimal] = []
    for value in values:
        normalized = value.quantize(Decimal('0.1'))
        if normalized not in unique_values:
            unique_values.append(normalized)
    while len(unique_values) < 4:
        candidate = (correct_value + Decimal(_random.choice([-8, -5, -3, 3, 5, 8]))).quantize(Decimal('0.1'))
        if candidate > 0 and candidate not in unique_values:
            unique_values.append(candidate)

    option_values = unique_values[:4]
    _random.shuffle(option_values)
    option_codes = ['A', 'B', 'C', 'D']
    correct_index = option_values.index(correct_value.quantize(Decimal('0.1')))

    return {
        'type': 'single',
        'stem': stem,
        'material': material,
        'options': [
            {'option_code': code, 'content': f'{value.normalize()}{suffix}'}
            for code, value in zip(option_codes, option_values)
        ],
        'difficulty': str(difficulty),
        'full_score': '1',
        'answer_data': {'correct': option_codes[correct_index]},
        'analysis': analysis,
    }


def _generate_growth_rate(stage: str, params: dict[str, Any]) -> ChallengeGeneratedQuestion:
    """
    生成增长率题

    :param stage: 难度阶段
    :param params: 生成参数
    :return:
    """
    ranges = {
        'stage_1': (80, 260, 5, 30),
        'stage_2': (180, 900, 8, 45),
        'stage_3': (500, 1800, 10, 55),
        'stage_4': (800, 2800, 12, 65),
    }
    base_min, base_max, rate_min, rate_max = ranges.get(stage, ranges['stage_2'])
    base = Decimal(_random.randint(base_min, base_max))
    rate = Decimal(_random.randint(rate_min, rate_max))
    current = (base * (Decimal('1') + rate / Decimal('100'))).quantize(Decimal('0.1'))
    values = [rate, rate + Decimal('3'), rate - Decimal('3'), rate + Decimal('6')]
    return _build_single_choice_question(
        stem='与基期相比，该指标的增长率约为多少？',
        values=values,
        correct_value=rate,
        analysis='增长率 =（现期量 - 基期量）÷ 基期量。',
        material=f'某指标基期为 {base.normalize()}，现期为 {current.normalize()}。',
        difficulty=Decimal(
            {'stage_1': '1.5', 'stage_2': '2.8', 'stage_3': '3.6', 'stage_4': '4.1'}.get(stage, '2.8')
        ),
        suffix='%',
    )


def _generate_base_value(stage: str, params: dict[str, Any]) -> ChallengeGeneratedQuestion:
    """
    生成基期量题

    :param stage: 难度阶段
    :param params: 生成参数
    :return:
    """
    current = Decimal(_random.randint(120, 1600))
    rate = Decimal(_random.randint(5, 45))
    base = (current / (Decimal('1') + rate / Decimal('100'))).quantize(Decimal('0.1'))
    values = [base, base + Decimal('10'), base - Decimal('10'), base + Decimal('20')]
    return _build_single_choice_question(
        stem='该指标的基期量约为多少？',
        values=values,
        correct_value=base,
        analysis='基期量 = 现期量 ÷（1 + 增长率）。',
        material=f'某指标现期为 {current.normalize()}，同比增长 {rate.normalize()}%。',
        difficulty=Decimal(
            {'stage_1': '1.8', 'stage_2': '3.0', 'stage_3': '3.8', 'stage_4': '4.3'}.get(stage, '3.0')
        ),
    )


def _generate_growth_amount(stage: str, params: dict[str, Any]) -> ChallengeGeneratedQuestion:
    """
    生成增长量题

    :param stage: 难度阶段
    :param params: 生成参数
    :return:
    """
    base = Decimal(_random.randint(100, 1800))
    rate = Decimal(_random.randint(6, 50))
    amount = (base * rate / Decimal('100')).quantize(Decimal('0.1'))
    current = base + amount
    values = [amount, amount + Decimal('8'), amount - Decimal('8'), amount + Decimal('15')]
    return _build_single_choice_question(
        stem='该指标比基期增加了约多少？',
        values=values,
        correct_value=amount,
        analysis='增长量 = 现期量 - 基期量，也可用基期量 × 增长率。',
        material=f'某指标基期为 {base.normalize()}，现期为 {current.normalize()}。',
        difficulty=Decimal(
            {'stage_1': '1.6', 'stage_2': '2.7', 'stage_3': '3.6', 'stage_4': '4.0'}.get(stage, '2.7')
        ),
    )


def _generate_proportion(stage: str, params: dict[str, Any]) -> ChallengeGeneratedQuestion:
    """
    生成比重题

    :param stage: 难度阶段
    :param params: 生成参数
    :return:
    """
    total = Decimal(_random.randint(300, 2200))
    proportion = Decimal(_random.randint(12, 68))
    part = (total * proportion / Decimal('100')).quantize(Decimal('0.1'))
    values = [proportion, proportion + Decimal('4'), proportion - Decimal('4'), proportion + Decimal('8')]
    return _build_single_choice_question(
        stem='该部分占总体的比重约为多少？',
        values=values,
        correct_value=proportion,
        analysis='比重 = 部分量 ÷ 总体量。',
        material=f'某总体量为 {total.normalize()}，其中某部分为 {part.normalize()}。',
        difficulty=Decimal(
            {'stage_1': '1.7', 'stage_2': '3.1', 'stage_3': '3.8', 'stage_4': '4.2'}.get(stage, '3.1')
        ),
        suffix='%',
    )


def _format_decimal(value: Decimal) -> str:
    """
    格式化小数

    :param value: 数值
    :return:
    """
    text = format(value.normalize(), 'f')
    if '.' not in text:
        return text
    return text.rstrip('0').rstrip('.')


def _build_concept_options(
    correct_concept_id: str,
    concepts: list[dict[str, str]] | None = None,
) -> tuple[list[dict[str, str]], str]:
    """
    构建概念识别选项

    :param correct_concept_id: 正确概念 ID
    :param concepts: 可选概念范围
    :return:
    """
    concept_pool = concepts if concepts else DATA_ANALYSIS_CONCEPTS
    correct_concept = next(item for item in concept_pool if item['id'] == correct_concept_id)
    distractors = [item for item in concept_pool if item['id'] != correct_concept_id]
    selected_concepts = [correct_concept, *_random.sample(distractors, min(3, len(distractors)))]
    if len(selected_concepts) < 4:
        fallback_distractors = [
            item
            for item in DATA_ANALYSIS_CONCEPTS
            if item['id'] not in {concept['id'] for concept in selected_concepts}
        ]
        selected_concepts.extend(_random.sample(fallback_distractors, 4 - len(selected_concepts)))
    _random.shuffle(selected_concepts)

    option_codes = ['A', 'B', 'C', 'D']
    options = [
        {
            'option_code': code,
            'content': item['name'],
        }
        for code, item in zip(option_codes, selected_concepts)
    ]
    correct_index = selected_concepts.index(correct_concept)
    return options, option_codes[correct_index]


def _generate_concept_identification(stage: str, params: dict[str, Any]) -> ChallengeGeneratedQuestion:
    """
    生成资料分析概念识别题

    :param stage: 难度阶段
    :param params: 生成参数
    :return:
    """
    unit = str(params.get('unit') or _random.choice(['亿元', '万人次', '万件', '万辆']))
    subject = str(params.get('subject') or _random.choice(['全市快递业务量', '某市新能源汽车产量', '全省文旅收入', '某平台订单量']))
    current_year = int(params.get('current_year') or _random.randint(2024, 2026))
    base_year = current_year - 1
    current_month = int(params.get('current_month') or _random.randint(3, 12))
    previous_month = current_month - 1

    base_value = Decimal(_random.randint(80, 260))
    annual_growth_amount = Decimal(_random.randint(12, 68))
    current_value = base_value + annual_growth_amount
    annual_growth_rate = (annual_growth_amount / base_value * Decimal('100')).quantize(Decimal('0.1'))
    raw_concept_ids = params.get('concept_ids')
    concept_ids = [str(item) for item in raw_concept_ids] if isinstance(raw_concept_ids, list) else []
    allowed_concepts = [item for item in DATA_ANALYSIS_CONCEPTS if item['id'] in concept_ids]
    allowed_concept_ids = {item['id'] for item in allowed_concepts}

    previous_month_value = Decimal(_random.randint(20, 90))
    monthly_change = Decimal(_random.randint(3, 18))
    if stage != 'stage_1' and _random.choice([True, False]):
        monthly_change = -monthly_change
    current_month_value = previous_month_value + monthly_change
    if current_month_value <= 0:
        current_month_value = previous_month_value + abs(monthly_change)
        monthly_change = abs(monthly_change)

    change_action = '增加' if monthly_change >= 0 else '减少'
    change_text = _format_decimal(abs(monthly_change))
    monthly_change_rate = (abs(monthly_change) / previous_month_value * Decimal('100')).quantize(Decimal('0.1'))

    target_items = [
        {
            'concept_id': 'base_value',
            'variants': [
                {
                    'content': f'{base_year} 年同期为 {_format_decimal(base_value)}{unit}',
                    'passage_line': f'{base_year} 年同期为 {_format_decimal(base_value)}{unit}。',
                },
                {
                    'content': f'用于比较的基础数值为 {_format_decimal(base_value)}{unit}',
                    'passage_line': f'用于比较的基础数值为 {_format_decimal(base_value)}{unit}。',
                },
            ],
        },
        {
            'concept_id': 'current_value',
            'variants': [
                {
                    'content': f'{current_year} 年上半年为 {_format_decimal(current_value)}{unit}',
                    'passage_line': f'{current_year} 年上半年，{subject}为 {_format_decimal(current_value)}{unit}。',
                },
                {
                    'content': f'报告期内达到 {_format_decimal(current_value)}{unit}',
                    'passage_line': f'报告期内，{subject}达到 {_format_decimal(current_value)}{unit}。',
                },
            ],
        },
        {
            'concept_id': 'growth_amount',
            'variants': [
                {
                    'content': f'比 {base_year} 年同期增加 {_format_decimal(annual_growth_amount)}{unit}',
                    'passage_line': f'比 {base_year} 年同期增加 {_format_decimal(annual_growth_amount)}{unit}。',
                },
                {
                    'content': f'现期相较基础数值多出 {_format_decimal(annual_growth_amount)}{unit}',
                    'passage_line': f'现期相较基础数值多出 {_format_decimal(annual_growth_amount)}{unit}。',
                },
            ],
        },
        {
            'concept_id': 'change_amount',
            'variants': [
                {
                    'content': f'比 {previous_month} 月{change_action} {change_text}{unit}',
                    'passage_line': (
                        f'{current_year} 年 {current_month} 月该指标为 {_format_decimal(current_month_value)}{unit}，'
                        f'比 {previous_month} 月{change_action} {change_text}{unit}。'
                    ),
                },
                {
                    'content': f'相邻统计期之间相差 {change_text}{unit}',
                    'passage_line': f'相邻统计期之间相差 {change_text}{unit}。',
                },
            ],
        },
        {
            'concept_id': 'change_rate',
            'variants': [
                {
                    'content': f'变化幅度为 {_format_decimal(monthly_change_rate)}%',
                    'passage_line': f'变化幅度为 {_format_decimal(monthly_change_rate)}%。',
                },
                {
                    'content': f'{change_action}幅度为 {_format_decimal(monthly_change_rate)}%',
                    'passage_line': f'相较上一统计期{change_action}幅度为 {_format_decimal(monthly_change_rate)}%。',
                },
            ],
        },
        {
            'concept_id': 'growth_rate',
            'variants': [
                {
                    'content': f'增长率为 {_format_decimal(annual_growth_rate)}%',
                    'passage_line': f'增长率为 {_format_decimal(annual_growth_rate)}%。',
                },
                {
                    'content': f'增长量占基础数值的 {_format_decimal(annual_growth_rate)}%',
                    'passage_line': f'增长量占基础数值的 {_format_decimal(annual_growth_rate)}%。',
                },
            ],
        },
        {
            'concept_id': 'yoy',
            'variants': [
                {
                    'content': f'比 {base_year} 年同期',
                    'passage_line': f'统计口径为比 {base_year} 年同期。',
                },
                {
                    'content': '与上一年同一时期相比',
                    'passage_line': '统计口径为与上一年同一时期相比。',
                },
            ],
        },
        {
            'concept_id': 'mom',
            'variants': [
                {
                    'content': f'比 {previous_month} 月',
                    'passage_line': f'统计口径为比 {previous_month} 月。',
                },
                {
                    'content': '与上一统计周期相比',
                    'passage_line': '统计口径为与上一统计周期相比。',
                },
            ],
        },
    ]
    if allowed_concepts:
        target_items = [item for item in target_items if item['concept_id'] in allowed_concept_ids]
        concept_order = {concept_id: index for index, concept_id in enumerate(concept_ids)}
        target_items.sort(key=lambda item: concept_order.get(str(item['concept_id']), len(concept_order)))
    if not target_items:
        raise errors.RequestError(msg='概念识别题生成参数 concept_ids 无可用概念')

    question_index = params.get('question_index')
    if isinstance(question_index, int):
        target_item = target_items[question_index % len(target_items)]
        variant_index = question_index // len(target_items)
    else:
        target_item = _random.choice(target_items)
        variant_index = _random.randint(0, 1)

    def get_variant(item: dict[str, Any]) -> dict[str, str]:
        """
        获取概念题干变体

        :param item: 概念题干配置
        :return:
        """
        variants = item['variants']
        return variants[variant_index % len(variants)]

    passage_items = target_items if allowed_concepts else target_items[:5]
    passage = '\n'.join(get_variant(item)['passage_line'] for item in passage_items)
    target_variant = get_variant(target_item)
    options, correct_option_code = _build_concept_options(
        str(target_item['concept_id']),
        allowed_concepts or None,
    )
    correct_concept = next(item for item in DATA_ANALYSIS_CONCEPTS if item['id'] == target_item['concept_id'])
    stem = '\n'.join([
        passage,
        f"其中“{target_variant['content']}”属于什么概念？",
    ])

    return {
        'type': 'single',
        'stem': stem,
        'material': None,
        'options': options,
        'difficulty': str(
            Decimal(
                {'stage_1': '1.0', 'stage_2': '1.5', 'stage_3': '1.8', 'stage_4': '2.0'}.get(stage, '1.0')
            )
        ),
        'full_score': '1',
        'answer_data': {
            'correct': correct_option_code,
        },
        'analysis': f"“{target_variant['content']}”对应{correct_concept['name']}，{correct_concept['definition']}。",
    }


GENERATOR_REGISTRY: dict[str, ChallengeGenerator] = {
    'data_analysis_concept_identification_v1': _generate_concept_identification,
    'data_analysis_concept_matching_v1': _generate_concept_identification,
    'data_analysis_growth_rate_v1': _generate_growth_rate,
    'data_analysis_base_value_v1': _generate_base_value,
    'data_analysis_growth_amount_v1': _generate_growth_amount,
    'data_analysis_proportion_v1': _generate_proportion,
}


def generate_challenge_question(
    *,
    generator_key: str,
    stage: str,
    params: dict[str, Any] | None = None,
) -> ChallengeGeneratedQuestion:
    """
    调用已注册的闯关题目生成器

    :param generator_key: 生成器标识
    :param stage: 难度阶段
    :param params: 生成参数
    :return:
    """
    generator = GENERATOR_REGISTRY.get(generator_key)
    if generator is None:
        raise errors.RequestError(msg=f'未注册的闯关题目生成器: {generator_key}')
    return generator(stage, params or {})
