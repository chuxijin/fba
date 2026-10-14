from random import Random

from backend.app.gongkao.schema.calculation_practice import (
    MAX_SAFE_INTEGER,
    BasicCalculationQuestion,
    BasicCustomConfig,
    BasicType,
    PerformanceThresholds,
)
from backend.app.gongkao.service.calculation.common import integer, rounded

BASIC_TYPES = (
    ('two_digit_add_sub', '两位数加减', '两位数加法和减法混合出现，适合热身和基础口算训练。', 12),
    ('round_hundred', '凑整百练习', '围绕补数和凑整百设计，训练资料分析里常用的快速拆分。', 10),
    ('three_digit_add', '三位数加法', '三位数连续加法训练，重点练进位稳定性和数字保持。', 18),
    ('three_digit_sub', '三位数减法', '三位数减法训练，重点练退位判断和差值敏感度。', 18),
    ('three_digit_add_sub', '三位数加减', '三位数加减混合训练，提升连续运算时的抗干扰能力。', 26),
    ('multi_add', '多数相加', '多个数字连续相加，训练分组、归并和短时记忆。', 32),
    ('mixed_add_sub', '混合加减', '加减随机混排，训练快速识别符号并选择计算路径。', 24),
    ('two_digit_mul_one', '两位数乘一位数', '基础乘法拆分训练，为更复杂乘法和估算打底。', 14),
    ('three_digit_mul_one', '三位数乘一位数', '三位数乘一位数，强化拆位乘法和进位处理。', 18),
    ('mul_11', '两位数乘11', '练习乘 11 的规律速算，适合建立数字结构感。', 10),
    ('mul_15', '两位数乘15', '练习乘 15 的拆分算法，提高特定倍数的速算能力。', 14),
    ('two_digit_mul_two', '两位数乘两位数', '两位数乘法训练，重点练拆分、交叉计算和校验。', 28),
    ('three_digit_div_one', '三位数除一位数', '基础除法训练，强化商的判断和余数处理。', 26),
    ('three_digit_div_two', '三位数除两位数', '两位数除法训练，重点练试商、估商和修正。', 38),
    ('estimate_mul', '乘法估算', '将两个因数分别四舍五入到整十后相乘。', 18),
    ('five_digit_div_three', '五位数除三位数', '大数除法估算，训练比例、倍数类计算的速度。', 55),
    ('three_digit_div_four', '三位数除四位数', '小数型除法关系训练，提升比值、占比和增长率敏感度。', 28),
    ('custom', '自定义', '自由设置数字位数、运算类型和题量，适合针对性补弱。', 12),
)


def get_thresholds(type_key: BasicType, count: int, config: BasicCustomConfig) -> PerformanceThresholds:
    base = next(item[3] for item in BASIC_TYPES if item[0] == type_key)
    if type_key == 'custom':
        if config.mode == 'power':
            base = min(60, 18 + config.first_digits * 4)
        else:
            second_digits = config.second_digits
            if config.second_mode == 'fixed':
                second_digits = len(str(config.fixed_second))
            elif config.second_mode == 'range':
                second_digits = len(str(config.range_end))
            weights = {'+': 1, '-': 1.05, '×': 1.45, '÷': 1.9}
            weight = sum(weights[operator] for operator in config.operators) / len(config.operators)
            base = max(8, min(60, integer(12 * weight * max(0.7, (config.first_digits + second_digits) / 4))))
    factor = 1 if count <= 10 else 1.05 if count <= 20 else 1.08 if count <= 30 else 1.12 if count <= 50 else 1.15
    excellent = max(1, integer(base * factor))
    good = max(excellent + 1, integer(base * 1.25 * factor))
    return PerformanceThresholds(**{
        'excellent': excellent,
        'good': good,
        'pass': max(good + 1, integer(base * 1.55 * factor)),
    })


def _binary(first: int, second: int, operator: str) -> BasicCalculationQuestion:
    if operator == '-':
        first, second = max(first, second), min(first, second)
        answer = first - second
    elif operator == '×':
        answer = first * second
    else:
        answer = first + second
    expression = f'{first}{operator}{second}='
    return BasicCalculationQuestion(expression=expression, answer=answer, explanation=[f'{expression}{answer}'])


def _division(dividend: int, divisor: int) -> BasicCalculationQuestion:
    answer = rounded(dividend / divisor, 2)
    return BasicCalculationQuestion(
        expression=f'{dividend}÷{divisor}≈',
        answer=answer,
        relative_tolerance=0.05,
        explanation=[f'{dividend} ÷ {divisor} ≈ {answer:.2f}，答案允许 ±5% 相对误差。'],
    )


def _non_divisible(rng: Random, low: int, high: int, divisor: int) -> int:
    value = rng.randint(low, high)
    if value % divisor == 0:
        value += 1 if value < high else -1
    return value


def _custom(rng: Random, config: BasicCustomConfig) -> BasicCalculationQuestion:
    first_min, first_max = 10 ** (config.first_digits - 1), 10**config.first_digits - 1
    if config.second_mode == 'fixed':
        second = config.fixed_second
    elif config.second_mode == 'range':
        second = rng.randint(config.range_start, config.range_end)
    else:
        second = rng.randint(10 ** (config.second_digits - 1), 10**config.second_digits - 1)
    if config.mode == 'power':
        exponent = max(2, min(4, second))
        # 答案作为 JSON number 传给小程序，必须在 JS 安全整数范围内。
        first_max = min(first_max, int(MAX_SAFE_INTEGER ** (1 / exponent)))
        first = rng.randint(first_min, first_max)
        return BasicCalculationQuestion(
            expression=f'{first}^{exponent}=',
            answer=first**exponent,
            explanation=[f'{first} 的 {exponent} 次方 = {first**exponent}'],
        )
    operator = rng.choice(config.operators)
    if operator == '÷':
        divisor = max(2, second)
        return _division(_non_divisible(rng, first_min, first_max, divisor), divisor)
    return _binary(rng.randint(first_min, first_max), second, operator)


def _add_sub(rng: Random, type_key: BasicType) -> BasicCalculationQuestion:
    if type_key == 'three_digit_add':
        return _binary(rng.randint(100, 899), rng.randint(100, 899), '+')
    if type_key == 'three_digit_sub':
        first = rng.randint(200, 999)
        return _binary(first, rng.randint(100, first - 1), '-')
    if type_key == 'two_digit_add_sub':
        return _binary(rng.randint(10, 99), rng.randint(10, 99), rng.choice(('+', '-')))
    if type_key == 'multi_add':
        values = [rng.randint(20, 199) for _ in range(4)]
        expression, answer = '+'.join(map(str, values)) + '=', sum(values)
    elif type_key == 'three_digit_add_sub':
        first, second, third = rng.randint(100, 700), rng.randint(100, 299), rng.randint(40, 199)
        expression = f'{first}+{second}-{third}=' if rng.random() > 0.5 else f'{first}-{third}+{second}='
        answer = first + second - third
    else:
        first, second, third = rng.randint(80, 300), rng.randint(20, 120), rng.randint(20, 120)
        expression, answer = f'{first}+{second}-{third}=', first + second - third
    return BasicCalculationQuestion(expression=expression, answer=answer, explanation=[f'{expression}{answer}'])


def create_basic(rng: Random, type_key: BasicType, config: BasicCustomConfig) -> BasicCalculationQuestion:
    if type_key == 'custom':
        return _custom(rng, config)
    if type_key == 'round_hundred':
        base, difference = rng.randint(1, 8) * 100, rng.randint(11, 89)
        return BasicCalculationQuestion(
            expression=f'{base - difference}+□={base}',
            answer=difference,
            explanation=[f'{base} - {base - difference} = {difference}'],
        )
    multiplication = {
        'two_digit_mul_one': (12, 99, 2, 9),
        'three_digit_mul_one': (101, 999, 2, 9),
        'mul_11': (12, 99, 11, 11),
        'mul_15': (12, 99, 15, 15),
        'two_digit_mul_two': (12, 99, 12, 99),
    }
    if type_key in multiplication:
        low_a, high_a, low_b, high_b = multiplication[type_key]
        return _binary(rng.randint(low_a, high_a), rng.randint(low_b, high_b), '×')
    division = {
        'three_digit_div_one': (100, 999, 2, 9),
        'three_digit_div_two': (100, 999, 11, 99),
        'five_digit_div_three': (10000, 99999, 101, 999),
        'three_digit_div_four': (100, 999, 1000, 9999),
    }
    if type_key in division:
        low_a, high_a, low_b, high_b = division[type_key]
        divisor = rng.randint(low_b, high_b)
        return _division(_non_divisible(rng, low_a, high_a, divisor), divisor)
    if type_key == 'estimate_mul':
        first, second = rng.randint(21, 98), rng.randint(21, 98)
        left, right = integer(first / 10) * 10, integer(second / 10) * 10
        return BasicCalculationQuestion(
            expression=f'{first}×{second}≈',
            answer=left * right,
            explanation=[f'分别取整十：{first} ≈ {left}，{second} ≈ {right}；{left} × {right} = {left * right}。'],
        )
    return _add_sub(rng, type_key)
