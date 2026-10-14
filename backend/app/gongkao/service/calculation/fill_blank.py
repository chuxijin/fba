from backend.app.gongkao.schema.calculation_practice import (
    CompareAnswer,
    FillBlankQuestion,
    FillBlankType,
    FractionDisplay,
)
from backend.app.gongkao.service.calculation.common import CalculationRandom, integer, number_text, rounded

FILL_BLANK_TYPES = (
    ('base_value', '估算前期量', '增长相关', True),
    ('growth_amount', '估算增长量', '增长相关', True),
    ('percent_convert', '百化分计算', '增长相关', False),
    ('growth_compare', '增量比大小', '增长相关', True),
    ('base_compare', '基期比大小', '增长相关', True),
    ('avg_growth_rate', '年均增长率', '增长相关', False),
    ('fraction_lt', '分数计算（分子<分母）', '比重相关', True),
    ('fraction_gt', '分数计算（分子>分母）', '比重相关', True),
    ('base_ratio', '基期比重', '比重相关', True),
    ('fraction_compare', '分数比大小', '比重相关', True),
    ('yearly_average', '年平均量', '比重相关', False),
)


def _tolerance(random: CalculationRandom, base: float) -> float:
    return 0.05


def _fraction(numerator: float, denominator: float, suffix: str | None = None) -> FractionDisplay:
    return FractionDisplay(numerator=number_text(numerator), denominator=number_text(denominator), suffix=suffix)


def _comparison(random: CalculationRandom, key: FillBlankType) -> FillBlankQuestion:
    displays = []
    values = []
    for _ in range(2):
        if key == 'fraction_compare':
            numerator, denominator = random.fraction(less_than_one=True)
            display = _fraction(numerator, denominator)
            value = numerator / denominator
        else:
            numerator, rate = random.value(100, 9999), random.biased_rate()
            denominator = rounded(1 + rate / 100, 3)
            display = _fraction(numerator, denominator)
            value = numerator / denominator
            if key == 'growth_compare':
                display.suffix = f'× {number_text(rate)}%'
                value *= rate / 100
        displays.append(display)
        values.append(value)
    answer: CompareAnswer = (
        'equal' if abs(values[0] - values[1]) < 1e-9 else 'greater' if values[0] > values[1] else 'less'
    )
    symbol = {'greater': '>', 'less': '<', 'equal': '='}[answer]
    return FillBlankQuestion(
        type_key=key,
        question_type='compare',
        display_mode='compare',
        left_display=displays[0],
        right_display=displays[1],
        compare_answer=answer,
        explanation=[f'左式约为 {rounded(values[0], 6)}，右式约为 {rounded(values[1], 6)}，左式 {symbol} 右式。'],
    )


def _growth(random: CalculationRandom, key: FillBlankType) -> FillBlankQuestion:
    current = random.value(100, 9999)
    negative = key == 'growth_amount' and random.rng.random() > 0.5
    rate = random.biased_rate(90 if negative else 108) * (-1 if negative else 1)
    if random.bias == 'allocation':
        current, rate, _ = random.allocation_values(1000, 9999)
        negative = False
    divisor = rounded(1 + rate / 100, 3)
    if key == 'base_value':
        answer = current / divisor
        return FillBlankQuestion(
            type_key=key,
            expression=f'{current}/{number_text(divisor)}≈',
            hint=f'现期：{current}，增长率：{number_text(rate)}%',
            tolerance=_tolerance(random, 0.03),
            answer=answer,
            explanation=[f'基期 = 现期 ÷ (1 + 增长率) = {current} ÷ {number_text(divisor)} ≈ {answer}。'],
        )
    answer = current * (rate / 100) / divisor
    return FillBlankQuestion(
        type_key=key,
        expression=f'现期:{current}  增长率:{number_text(rate)}%',
        hint='求增长量',
        sub_hint='需要负号时会自动生成' if negative else None,
        tolerance=_tolerance(random, 0.03),
        answer=answer,
        answer_prefix='-' if negative else None,
        explanation=[f'增长量 = {current} × {number_text(rate)}% ÷ {number_text(divisor)} ≈ {answer}。'],
    )


def _ratio(random: CalculationRandom) -> FillBlankQuestion:
    part_rate, whole_rate = random.biased_rate(), random.biased_rate()
    part = random.value(100, 999)
    part_divisor, whole_divisor = rounded(1 + part_rate / 100, 3), rounded(1 + whole_rate / 100, 3)
    # 两期都应满足部分量 < 整体量。
    minimum_whole = max(part + 50, int(part * whole_divisor / part_divisor) + 1)
    whole = random.rng.randint(minimum_whole, max(minimum_whole, part * 3))
    answer = part / whole * whole_divisor / part_divisor
    return FillBlankQuestion(
        type_key='base_ratio',
        display_mode='double_fraction',
        left_display=_fraction(part, whole),
        right_display=_fraction(whole_divisor, part_divisor),
        expression_suffix='≈',
        hint=f'A: {part}，{number_text(part_rate)}% ; B: {whole}，{number_text(whole_rate)}%',
        tolerance=_tolerance(random, 0.03),
        answer=answer,
        explanation=[f'基期比重 = (部分现期 / 整体现期) × (1 + 整体增长率) / (1 + 部分增长率) ≈ {answer}。'],
    )


def create_fill_blank(random: CalculationRandom, key: FillBlankType) -> FillBlankQuestion:
    if key in ('growth_compare', 'base_compare', 'fraction_compare'):
        return _comparison(random, key)
    if key in ('base_value', 'growth_amount'):
        return _growth(random, key)
    if key == 'base_ratio':
        return _ratio(random)
    if key in ('fraction_lt', 'fraction_gt'):
        numerator, denominator = random.fraction(less_than_one=key == 'fraction_lt')
        answer = numerator / denominator
        return FillBlankQuestion(
            type_key=key,
            display_mode='fraction',
            left_display=_fraction(numerator, denominator),
            expression_suffix='≈',
            hint='建议写到小数点后2~3位',
            tolerance=_tolerance(random, 0.02),
            answer=answer,
            explanation=[f'{numerator} ÷ {denominator} ≈ {answer}。'],
        )
    if key == 'percent_convert':
        low, high = {'easy': (2, 10), 'normal': (3, 20), 'hard': (7, 35)}[random.difficulty]
        denominator = random.rng.randint(low, high)
        numerator = random.rng.randint(1, min(denominator - 1, 9))
        answer = numerator / denominator * 100
        return FillBlankQuestion(
            type_key=key,
            expression=f'{numerator}/{denominator}≈%',
            hint='写到小数点后一位即可',
            tolerance=_tolerance(random, 0.02),
            answer=answer,
            explanation=[f'{numerator} ÷ {denominator} × 100% ≈ {number_text(answer)}%。'],
        )
    if key == 'avg_growth_rate':
        years = random.rng.randint(3, 5 if random.difficulty == 'easy' else 8)
        base = random.value(100, 3000)
        end = integer(base * (1 + random.rate(20, 150) / 100))
        answer = ((end / base) ** (1 / years) - 1) * 100
        return FillBlankQuestion(
            type_key=key,
            expression='年均增长率≈_____%',
            hint=f'基期{base}，末期{end}，共{years}年',
            tolerance=_tolerance(random, 0.05),
            answer=answer,
            explanation=[f'年均增长率 = [({end}/{base})^(1/{years}) - 1] × 100% ≈ {number_text(answer)}%。'],
        )
    total, years = random.value(500, 99999), random.rng.randint(3, 10)
    answer = total / years
    return FillBlankQuestion(
        type_key=key,
        expression=f'{total}/{years}≈',
        hint=f'{years}年累计{total}，求年平均量',
        tolerance=_tolerance(random, 0.03),
        answer=answer,
        explanation=[f'年平均量 = {total} ÷ {years} ≈ {answer}。'],
    )
