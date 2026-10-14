import math

from dataclasses import dataclass
from random import Random

from backend.app.gongkao.schema.calculation_practice import CalcDifficulty, CalcMethodBias

GENERATOR_VERSION = '1.1.0'
CHAR_FRACTIONS = (
    (2, 50),
    (3, 33.3),
    (4, 25),
    (5, 20),
    (6, 16.7),
    (7, 14.3),
    (8, 12.5),
    (9, 11.1),
    (10, 10),
    (11, 9.1),
    (12, 8.3),
    (13, 7.7),
    (14, 7.1),
    (15, 6.7),
    (16, 6.25),
    (17, 5.9),
    (18, 5.6),
    (19, 5.3),
    (20, 5),
    (25, 4),
    (30, 3.3),
    (33, 3),
    (40, 2.5),
    (45, 2.2),
    (50, 2),
)
SCALING_DIV_TARGETS = (100, 150, 200, 250, 300, 350, 400, 500, 600, 670, 750, 1000)
SCALING_MUL_TARGETS = (1500, 2000, 2500, 3000, 4000, 5000, 6000, 8000)


def rounded(value: float, digits: int = 0) -> float:
    """保留原小程序 Math.round 的半入规则，避免 Python 银行家舍入造成迁移差异。"""
    factor = 10**digits
    return math.floor(value * factor + 0.5) / factor


def integer(value: float) -> int:
    return math.floor(value + 0.5)


def number_text(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


@dataclass(frozen=True)
class DifficultyConfig:
    friendly_rate: float
    decimal_rate: float
    option_gap: tuple[float, float]


DIFFICULTIES = {
    'easy': DifficultyConfig(0.1, 0.85, (0.15, 0.20)),
    'normal': DifficultyConfig(0.1, 0.85, (0.09, 0.11)),
    'hard': DifficultyConfig(0.1, 0.85, (0.045, 0.055)),
}


class CalculationRandom:
    """每个题单独立的随机状态，禁止跨请求共享或修改全局随机种子。"""

    def __init__(self, seed: int, difficulty: CalcDifficulty = 'normal', bias: CalcMethodBias = 'auto') -> None:
        self.rng = Random(seed)
        self.difficulty = difficulty
        self.bias = bias
        self.config = DIFFICULTIES[difficulty]

    def value(self, minimum: int, maximum: int) -> int:
        """先选位数再抽整数，避免五位数淹没三位数，也不把位数当难度。"""
        buckets = [(max(minimum, 10**n), min(maximum, 10 ** (n + 1) - 1)) for n in range(6)]
        low, high = self.rng.choice([(low, high) for low, high in buckets if low <= high])
        return self.rng.randint(low, high)

    def characteristic_rate(self, max_error: float = 0.04) -> tuple[int, float]:
        """扰动真实的 1/n；同时校验增长与下降量近似，不直接给特征百分数。"""
        candidates = []
        for n, _ in CHAR_FRACTIONS:
            for tick in range(math.ceil(1000 / n * 0.94), math.floor(1000 / n * 1.06) + 1):
                rate = tick / 10
                if abs(rate - rounded(100 / n, 1)) < 0.05:
                    continue
                # 下降时用现期/(n-1)，正增长时用现期/(n+1)。
                errors = [abs((100 + sign * rate) / ((n + sign) * rate) - 1) for sign in (-1, 1)]
                if max(errors) <= max_error:
                    candidates.append((n, rate))
        return self.rng.choice(candidates)

    def allocation_values(self, minimum: int = 1000, maximum: int = 99999) -> tuple[int, float, int]:
        """让一次余差修正对基期、增长量均适用，而不只是给随机题贴标签。"""
        for _ in range(200):
            current = self.value(minimum, maximum)
            rate = self.rng.randint(21, 149) / 10
            r = rate / 100
            base = current / (1 + r)
            step = 10 ** max(1, math.floor(math.log10(base)) - 1)
            assumed = integer(base / step) * step
            residual = current - assumed * (1 + r)
            estimate = assumed + residual * (1 - r)
            if abs(estimate - base) <= 0.01 * min(base, current - base):
                return current, rate, assumed
        # 确定且满足约束的回退，不返回未经验证的数据。
        return 4100, 3.0, 4000

    def biased_rate(self, maximum: float = 108) -> float:
        """下降率调用时限制为 <100%，保证基期分母始终为正。"""
        for _ in range(80):
            rate = self._biased_rate()
            if 0 < rate <= maximum:
                return rate
        return min(37.3, maximum)

    def _biased_rate(self) -> float:
        bias = self.bias
        if bias == 'auto':
            roll = self.rng.random()
            bias = 'scaling_div' if roll < 0.4 else 'char_fraction' if roll < 0.65 else 'allocation'
        if bias == 'scaling_div':
            noise = {'easy': 0.02, 'normal': 0.05, 'hard': 0.08}[self.difficulty]
            target = self.rng.choice((1.1, 1.2, 1.25, 1.3, 1.33, 1.4, 1.5, 1.6, 1.75, 2))
            return rounded((max(1.01, target + self.rng.uniform(-noise, noise)) - 1) * 100, 1)
        if bias == 'char_fraction':
            return self.characteristic_rate(0.015 if self.difficulty == 'hard' else 0.035)[1]
        return self.rng.randint(21, 149) / 10

    def rate(self, minimum: int, maximum: int, *, use_bias: bool = False) -> float:
        if use_bias and self.bias != 'auto':
            # 比重与下降率都必须小于 100%；方法偏向优先于常规区间。
            return self.biased_rate(90)
        special = [rate for rate in (5, 10, 12.5, 16.7, 20, 25, 33.3, 40, 50, 60) if minimum <= rate <= maximum]
        if special and self.rng.random() < self.config.friendly_rate:
            return self.rng.choice(special)
        rate = float(self.rng.randint(minimum, maximum))
        if self.rng.random() < self.config.decimal_rate:
            rate = min(maximum, rate + self.rng.randint(1, 9) / 10)
        return rounded(rate, 1)

    def fraction(self, *, less_than_one: bool) -> tuple[int, int]:
        denominator = self.value(100, 999)
        if self.bias == 'scaling_div':
            denominator = self.rng.choice((150, 200, 250, 300, 400, 500, 600, 750, 800)) + self.rng.randint(-12, 12)
        if self.bias == 'char_fraction':
            low, high = {'easy': (2, 6), 'normal': (4, 10), 'hard': (7, 16)}[self.difficulty]
            n = self.rng.randint(low, high)
            if less_than_one:
                numerator = min(denominator - 1, max(10, integer(denominator / n) + self.rng.randint(-2, 2)))
            else:
                numerator = max(denominator + 1, integer(denominator * (1 + 1 / n)) + self.rng.randint(-3, 3))
        elif less_than_one:
            ratio = {'easy': 0.3, 'normal': 0.25, 'hard': 0.15}[self.difficulty]
            numerator = self.rng.randint(max(10, math.floor(denominator * ratio)), denominator - 1)
        else:
            ratio = {'easy': 2, 'normal': 2.5, 'hard': 3.5}[self.difficulty]
            numerator = self.rng.randint(denominator + 1, math.floor(denominator * ratio))
        return numerator, denominator

    def options(self, correct: float, digits: int = 0) -> tuple[list[float], int]:
        """有界地产生带符号的唯一选项，负数和零答案也能正常生成。"""
        scale = 10**digits
        correct_scaled = integer(correct * scale)
        values = [correct_scaled]
        low, high = self.config.option_gap
        # 最邻近选项按难度控制；零或极小答案退化为一个显示精度单位。
        step = max(1, integer(abs(correct_scaled) * self.rng.uniform(low, high)))
        position = self.rng.randint(0, 3)
        for direction, count in ((-1, position), (1, 3 - position)):
            distance = step
            for _ in range(count):
                values.append(correct_scaled + direction * distance)
                distance += max(1, integer(step * self.rng.uniform(1, 1.8)))
        self.rng.shuffle(values)
        return [value / scale for value in values], values.index(correct_scaled)
