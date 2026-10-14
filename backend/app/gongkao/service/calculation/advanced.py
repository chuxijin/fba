import math

from backend.app.gongkao.schema.calculation_practice import (
    AdvancedMethod,
    AdvancedMode,
    AdvancedOption,
    AdvancedQuestion,
    AllocationQuestion,
    CharFractionQuestion,
    DifferenceDataItem,
    DifferenceQuestion,
    RangeEstQuestion,
    ScalingDivQuestion,
    ScalingMulQuestion,
)
from backend.app.gongkao.service.calculation.common import (
    SCALING_DIV_TARGETS,
    SCALING_MUL_TARGETS,
    CalculationRandom,
    integer,
    number_text,
    rounded,
)

ADVANCED_METHODS = (
    ('scaling_div', '除法放缩'),
    ('scaling_mul', '乘法放缩'),
    ('allocation', '假设分配法'),
    ('range_est', '范围估算'),
    ('char_fraction', '特征分数'),
    ('difference', '差分法'),
    ('mixed_speed', '混合速算'),
)


def _options(
    random: CalculationRandom,
    correct: float,
    digits: int = 0,
) -> tuple[list[AdvancedOption], int]:
    """数值选择题复用统一间距策略，不再让旧干扰项绕过难度控制。"""
    values, index = random.options(correct, digits)
    options = [
        AdvancedOption(value=value, display=f'{value:.{digits}f}' if digits else number_text(value)) for value in values
    ]
    return options, index


def _scaling_div(random: CalculationRandom, mode: AdvancedMode) -> ScalingDivQuestion:
    rng = random.rng
    denominator, target = 373, 400
    for _ in range(80):
        low, high = rng.choice(((103, 145), (175, 245), (315, 395), (460, 540)))
        candidate = rng.randint(low, high)
        targets = [value for value in SCALING_DIV_TARGETS if 0.05 <= abs(value - candidate) / candidate <= 0.15]
        if targets:
            denominator, target = candidate, rng.choice(targets)
            break
    numerator = integer(denominator * rng.uniform(0.8, 1.8))
    delta = target - denominator
    delta_num = abs(delta) * numerator / denominator
    correct = rounded(numerator / denominator, 3)
    sign = '+' if delta >= 0 else '-'
    options, index = _options(random, correct, 3)
    return ScalingDivQuestion(
        mode=mode,
        numerator=numerator,
        denominator=denominator,
        target_denominator=target,
        delta_denominator=delta,
        correct_delta_num=delta_num,
        material=f'某指标 A 为 {numerator}，对应基准量 B 为 {denominator}。'
        + (f'为便于速算，将分母放缩到 {target}。' if mode == 'formula' else ''),
        question='填入分子同步改变量的绝对值' if mode == 'formula' else '估算原始比值 A/B 最接近以下哪一项？',
        answer_text=number_text(rounded(delta_num, 3)) if mode == 'formula' else f'{correct:.3f}',
        options=options if mode == 'question' else [],
        correct_index=index if mode == 'question' else -1,
        correct_value=correct,
        explanation=[
            f'分母从 {denominator} {sign} {abs(delta)} 调整到 {target}。',
            f'分子同步 {sign} {abs(delta)} × ({numerator}/{denominator})，改变量约为 {delta_num}。',
            f'原比值 {numerator}/{denominator} ≈ {correct:.3f}。',
        ],
    )


def _valid_multiplier(value: int) -> bool:
    ranges = ((105, 117), (118, 132), (135, 150), (155, 178), (190, 210), (235, 265), (310, 350), (470, 530))
    return value % 10 != 0 and all(not low <= value <= high for low, high in ranges)


def _scaling_mul(random: CalculationRandom, mode: AdvancedMode) -> ScalingMulQuestion:
    rng = random.rng
    target = integer(rng.choice(SCALING_MUL_TARGETS) * rng.choice((0.1, 1, 10)))
    deviation = rng.choice((-0.03, -0.02, -0.01, 0.01, 0.02, 0.03))
    fuzz = max(1, integer(target * 0.002))
    num_a = integer(target * (1 - deviation)) + rng.randint(-fuzz, fuzz)
    is_percent = rng.random() > 0.5
    maximum = 450 if is_percent and mode == 'question' else 900 if is_percent else 999
    candidates = [value for value in range(101, maximum + 1) if _valid_multiplier(value)]
    num_b = rng.choice(candidates) / (10 if is_percent else 1)
    delta_a = target - num_a
    delta_b = num_a * num_b / target - num_b
    suffix = '%' if is_percent else ''
    product = integer(num_a * num_b / (100 if is_percent else 1))
    options, index = _options(random, product)
    material = f'已知乘积式为 {num_a} × {number_text(num_b)}{suffix}，将因数 A 调整到 {target}。'
    question = '求 B 应同步改变多少个百分点？' if is_percent else '求因数 B 应同步改变多少？'
    if mode == 'question':
        if is_percent:
            material = f'某市生产总值为 {num_a} 亿元，其中高新技术产业产值占比为 {number_text(num_b)}%。'
            question = '该市高新技术产业产值约为多少亿元？'
        else:
            material = f'某学校采购 {number_text(num_b)} 台教学设备，单价为每台 {num_a} 元。'
            question = '这些设备的总花费约为多少元？'
    return ScalingMulQuestion(
        mode=mode,
        num_a=num_a,
        num_b=num_b,
        target_a=target,
        delta_a=delta_a,
        correct_delta_b=delta_b,
        is_percent_b=is_percent,
        material=material,
        question=question,
        answer_text=f'{delta_b:+g}{suffix}' if mode == 'formula' else str(product),
        options=options if mode == 'question' else [],
        correct_index=index if mode == 'question' else -1,
        correct_value=delta_b if mode == 'formula' else product,
        explanation=[
            f'保持乘积不变：{num_a} × B = {target} × (B + ΔB)。',
            f'ΔB = ({num_a}/{target} - 1) × {number_text(num_b)} ≈ {delta_b:+g}{suffix}。',
            f'原乘积 {num_a} × {number_text(num_b)}{suffix} ≈ {product}。',
        ],
    )


def _allocation(random: CalculationRandom, mode: AdvancedMode) -> AllocationQuestion:
    current, rate, assumed = random.allocation_values()
    base = integer(current / (1 + rate / 100))
    growth = current - base
    correction = base - assumed
    assumed_growth = integer(assumed * rate / 100)
    options, index = _options(random, base)
    return AllocationQuestion(
        mode=mode,
        current_value=current,
        rate_percent=rate,
        assumed_base=assumed,
        correction=correction,
        base_answer=base,
        growth_answer=growth,
        material=f'某地区本期完成量为 {current}，同比增长 {rate:.1f}%。',
        question='分别填入基期和变化量' if mode == 'formula' else '该地区上期完成量约为多少？',
        answer_text=f'基期 {base}，变化量 {growth}' if mode == 'formula' else str(base),
        options=options if mode == 'question' else [],
        correct_index=index if mode == 'question' else -1,
        correct_value=base,
        explanation=[
            f'先假设基期 {assumed}，对应变化量约为 {assumed_growth}。',
            f'假设现期 {assumed + assumed_growth}，与实际现期相差 {current - assumed - assumed_growth}。',
            f'误差按 1 + {rate:.1f}% 分配回基期：{current} ÷ {1 + rate / 100:.3f} ≈ {base}。',
            f'变化量 = {current} - {base} = {growth}。',
        ],
    )


def _range_est(random: CalculationRandom, mode: AdvancedMode) -> RangeEstQuestion:
    rng = random.rng
    truncated_num, truncated_den = 673, 11
    for _ in range(80):
        num, den = rng.randint(150, 949), rng.randint(11, 99)
        estimate = num / den
        if 15 <= estimate <= 94 and 0.8 <= estimate % 5 <= 4.2:
            truncated_num, truncated_den = num, den
            break
    estimate = truncated_num / truncated_den
    bin_start, leading = math.floor(estimate / 5) * 5, math.floor(estimate)
    position = rng.randint(0, 3)
    options = [
        AdvancedOption(value=start, display=f'[{start}, {start + 5})')
        for start in range(bin_start - position * 5, bin_start + (4 - position) * 5, 5)
    ]
    numerator, denominator = truncated_num * rng.choice((100, 1000, 10000)), truncated_den * rng.choice((10, 100))
    return RangeEstQuestion(
        mode=mode,
        numerator=numerator,
        denominator=denominator,
        truncated_numerator=truncated_num,
        truncated_denominator=truncated_den,
        estimate=rounded(estimate, 2),
        bin_start=bin_start,
        material=f'某指标现期值为 {numerator}，对应基准量为 {denominator}。',
        question='截位估算后，前两位填入' if mode == 'formula' else '截位商的前两位落在哪个区间？',
        answer_text=str(leading) if mode == 'formula' else options[position].display,
        options=options if mode == 'question' else [],
        correct_index=position if mode == 'question' else -1,
        correct_value=leading if mode == 'formula' else bin_start,
        explanation=[
            f'分子取前三位 {truncated_num}，分母取前两位 {truncated_den}。',
            f'{truncated_num} ÷ {truncated_den} ≈ {estimate:.2f}，前两位为 {leading}。',
            f'对应区间 [{bin_start}, {bin_start + 5})；原商的数量级另按截位倍数还原。',
        ],
    )


def _char_fraction(random: CalculationRandom, mode: AdvancedMode) -> CharFractionQuestion:
    for attempt in range(201):
        n, given = random.characteristic_rate() if attempt < 200 else (8, 12.6)
        current = random.value(1000, 80000) if attempt < 200 else 4103
        estimate = current / (n + 1)
        answer = integer(current * given / (100 + given))
        options, index = _options(random, answer)
        # 不只保证近似在容差内，还保证用该方法不会选到别的选项。
        if abs(estimate - answer) <= answer * 0.05 and (
            mode == 'formula'
            or all(
                abs(estimate - answer) < abs(estimate - option.value) for i, option in enumerate(options) if i != index
            )
        ):
            break
    return CharFractionQuestion(
        mode=mode,
        current_value=current,
        given_rate=given,
        exact_rate=100 / n,
        fraction_denom=n,
        correct_answer=answer,
        correct_value=answer,
        material=f'某地区本期完成值为 {current}，同比增长 {number_text(given)}%。',
        question='请计算同比增长量' if mode == 'formula' else '该地区同比增长量约为多少？',
        answer_text=str(answer),
        options=options if mode == 'question' else [],
        correct_index=index if mode == 'question' else -1,
        explanation=[
            f'{number_text(given)}% ≈ 1/{n}。',
            f'特征分数速算：增长量 ≈ {current} ÷ ({n} + 1) ≈ {rounded(estimate, 2)}。',
            f'按题干增长率核算：{current} × {number_text(given)}% / (1 + {number_text(given)}%) ≈ {answer}。',
        ],
    )


def _difference(random: CalculationRandom, mode: AdvancedMode) -> DifferenceQuestion:
    rng = random.rng
    highest = rng.random() > 0.5
    target_rate = rng.randint(50, 250) / 1000
    base_a = rng.randint(200, 800)
    base_b = base_a + rng.randint(30, 160)
    current_a = integer(base_a * (1 + target_rate))
    current_b = integer(base_b * (1 + target_rate + rng.uniform(-0.0015, 0.0015)))
    if (current_a - base_a) * base_b == (current_b - base_b) * base_a:
        current_b += 1
    pairs = [(current_a, base_a), (current_b, base_b)]
    # 其余两项放在同一侧，使接近的两个分式真正决定最大/最小值。
    for _ in range(2):
        base = rng.randint(150, 900)
        distant_rate = target_rate + (-1 if highest else 1) * rng.randint(30, 80) / 1000
        pairs.append((integer(base * (1 + distant_rate)), base))
    items = [
        DifferenceDataItem(label=label, current_value=current, base_value=base, rate=(current - base) / base)
        for label, (current, base) in zip(('甲', '乙', '丙', '丁'), pairs)
    ]
    close_a, close_b = items[:2]
    rng.shuffle(items)
    if mode == 'formula':
        for item, label in zip(items, 'ABCD'):
            item.label = label
    correct_item = (max if highest else min)(items, key=lambda item: item.rate)
    options = [AdvancedOption(value=ord(item.label), display=item.label) for item in items]
    index = items.index(correct_item)
    numerator_diff = (current_b - base_b) - (current_a - base_a)
    denominator_diff = base_b - base_a
    difference_rate = numerator_diff / denominator_diff
    relation = '>' if difference_rate > close_a.rate else '<'
    material = '；'.join(
        f'{item.label}: {item.current_value - item.base_value}/{item.base_value}'
        if mode == 'formula'
        else f'{item.label}地区：本期产值 {item.current_value} 亿元，上期 {item.base_value} 亿元'
        for item in items
    )
    return DifferenceQuestion(
        mode=mode,
        items=items,
        ask_highest=highest,
        correct_label=correct_item.label,
        material=material,
        question=f'选出数值最{"大" if highest else "小"}的分式'
        if mode == 'formula'
        else f'四个地区中，产值同比增长率最{"高" if highest else "低"}的是？',
        answer_text=correct_item.label,
        options=options,
        correct_index=index,
        correct_value=ord(correct_item.label),
        explanation=[
            f'先排除明显偏{"低" if highest else "高"}的两项，比较接近的 {close_a.label} 和 {close_b.label}。',
            f'分母 {base_b} > {base_a}，差分数 = {numerator_diff}/{denominator_diff} ≈ {difference_rate:.5f}。',
            f'差分数 {relation} {close_a.label} 的比值，因此 {close_b.label} {relation} {close_a.label}。',
            f'{close_a.label} ≈ {close_a.rate * 100:.3f}%，{close_b.label} ≈ {close_b.rate * 100:.3f}%。',
            f'答案：{correct_item.label}。',
        ],
    )


def create_advanced(random: CalculationRandom, method: AdvancedMethod, mode: AdvancedMode) -> AdvancedQuestion:
    creators = {
        'scaling_div': _scaling_div,
        'scaling_mul': _scaling_mul,
        'allocation': _allocation,
        'range_est': _range_est,
        'char_fraction': _char_fraction,
        'difference': _difference,
    }
    if method == 'mixed_speed':
        method = random.rng.choice(list(creators))
    return creators[method](random, mode)
