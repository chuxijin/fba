from backend.app.gongkao.schema.calculation_practice import DataPracticeQuestion, PracticeType
from backend.app.gongkao.service.calculation.common import CalculationRandom, integer, number_text, rounded

PRACTICE_TYPES = (
    ('random', '随机', True),
    ('base_value', '基期量', True),
    ('base_diff', '基期差', True),
    ('growth_amount', '增长量', True),
    ('growth_rate', '增长率', True),
    ('interval_growth_rate', '间隔增长率', False),
    ('avg_growth_rate', '平均数增长率', False),
    ('mixed_growth_rate', '混合增长率', False),
    ('diff_growth_rate', '差值增长率', False),
    ('annual_avg_rate', '年均增长率', False),
    ('current_proportion', '本期比重', True),
    ('base_proportion', '基期比重', True),
    ('proportion_diff', '两期比重差', False),
    ('partial_value', '部分量', False),
    ('average_value', '平均值', False),
    ('growth_contribution', '增长贡献率', False),
    ('pull_growth', '拉动增长', False),
)
INDICATORS = (
    ('G县', '小麦种植面积', '千公顷'),
    ('H市', '生产总值', '亿元'),
    ('A省', '外贸进出口总额', '万美元'),
    ('B区', '社会消费品零售总额', '亿元'),
    ('C市', '固定资产投资', '万元'),
    ('D县', '粮食产量', '万吨'),
    ('E省', '财政收入', '亿元'),
    ('F市', '旅游总收入', '万元'),
    ('全国', '快递业务量', '亿件'),
    ('全国', '货物运输量', '万吨'),
)


class DataPracticeGenerator:
    def __init__(self, random: CalculationRandom, key: PracticeType) -> None:
        self.random = random
        self.key = key
        self.region, self.indicator, self.unit = random.rng.choice(INDICATORS)
        self.year = random.rng.choice((2018, 2019, 2020, 2021, 2022, 2023))
        self.period = random.rng.choice(('1月', '2月', '3月', '上半年', '前三季度', '全年'))

    def result(
        self,
        *,
        material: str,
        question: str,
        numerator: str,
        answer: float,
        hint: str,
        operands: dict[str, float],
        denominator: str = '',
        digits: int = 0,
        unit: str = '',
    ) -> DataPracticeQuestion:
        answer = rounded(answer, digits)
        values, correct_index = self.random.options(answer, digits)
        options = [f'{number_text(value)}{unit}' for value in values]
        formula = f'({numerator}) / ({denominator})' if denominator else numerator
        return DataPracticeQuestion(
            type_key=self.key,
            material=material,
            question=f'问：{question}',
            formula_numerator=numerator,
            formula_denominator=denominator,
            options=options,
            correct_index=correct_index,
            answer=answer,
            answer_unit=unit,
            formula_hint=hint,
            operands=operands,
            explanation=[hint, f'{formula} ≈ {number_text(answer)}{unit}。'],
        )

    def base_or_growth(self) -> DataPracticeQuestion:
        r = self.random
        growth = r.rng.random() > 0.3
        rate = r.rate(5, 60 if self.key == 'base_value' else 50, use_bias=True) * (1 if growth else -1)
        current = r.value(1000, 99999)
        if r.bias == 'char_fraction':
            # 给显示取整留出余量，防止小增长量的舍入影响近邻选项判断。
            current = r.value(10000, 99999)
        if r.bias == 'allocation':
            current, rate, _ = r.allocation_values()
            growth = True
        base = current / (1 + rate / 100)
        sign, action = ('+', '增长') if growth else ('-', '减少')
        material = (
            f'{self.year}年{self.period}，{self.region}{self.indicator}为{current}{self.unit}，'
            f'同比{action}{number_text(abs(rate))}%。'
        )
        denominator = f'1 {sign} {number_text(abs(rate))}%'
        if self.key == 'base_value':
            question = f'{self.year - 1}年{self.period}，{self.region}{self.indicator}约为多少{self.unit}？'
            numerator, answer = str(current), base
            hint = '基期量 = 现期量 / (1 + 有符号增长率)'
        else:
            question = f'{self.year}年{self.period}，{self.region}{self.indicator}比上年同期{action}了多少{self.unit}？'
            numerator, answer = f'{current} × {number_text(abs(rate))}%', abs(current - base)
            hint = '增长/减少量的绝对值 = 现期量 × |增长率| / (1 + 有符号增长率)'
        return self.result(
            material=material,
            question=question,
            numerator=numerator,
            denominator=denominator,
            answer=answer,
            hint=hint,
            operands={'current': current, 'rate': rate},
            unit=self.unit,
        )

    def growth_rate(self) -> DataPracticeQuestion:
        r = self.random
        base = r.value(1000, 50000)
        rate = r.rate(5, 60, use_bias=True) * r.rng.choice((-1, 1, 1))
        current = integer(base * (1 + rate / 100))
        return self.result(
            material=f'{self.year - 1}年{self.period}，{self.region}{self.indicator}为{base}{self.unit}；'
            f'{self.year}年同期为{current}{self.unit}。',
            question=f'{self.year}年同期的同比增长率约为多少？',
            numerator=f'({current} - {base}) × 100%',
            denominator=str(base),
            answer=(current - base) / base * 100,
            digits=1,
            unit='%',
            hint='增长率 = (现期量 - 基期量) / 基期量，下降时为负值',
            operands={'current': current, 'base': base},
        )

    def differences(self) -> DataPracticeQuestion:
        r = self.random
        use_bias = self.key == 'base_diff'
        current_a = r.value(10000, 50000)
        rate_a, rate_b = r.rate(5, 30, use_bias=use_bias), r.rate(10, 40, use_bias=use_bias)
        # 保证基期差为正且远离零，避免差值增长率产生无定义/极端分母。
        max_b = min(current_a - 2000, int(current_a * (1 + rate_b / 100) / (1 + rate_a / 100) * 0.85))
        current_b = r.value(1000, max_b)
        base_a, base_b = current_a / (1 + rate_a / 100), current_b / (1 + rate_b / 100)
        base_diff = base_a - base_b
        formula = f'{current_a}/(1+{number_text(rate_a)}%) - {current_b}/(1+{number_text(rate_b)}%)'
        material = (
            f'{self.year}年{self.period}，{self.region}A产业产值{current_a}万元，同比增长{number_text(rate_a)}%；'
            f'B产业产值{current_b}万元，同比增长{number_text(rate_b)}%。'
        )
        operands = {'current_a': current_a, 'current_b': current_b, 'rate_a': rate_a, 'rate_b': rate_b}
        if self.key == 'base_diff':
            return self.result(
                material=material,
                question=f'{self.year - 1}年同期，A产业产值比B产业多多少万元？',
                numerator=formula,
                answer=base_diff,
                unit='万元',
                hint='基期差 = 基期A - 基期B',
                operands=operands,
            )
        return self.result(
            material=material,
            question='A、B产业产值之差的同比增长率约为多少？',
            numerator=f'({current_a} - {current_b} - ({formula})) × 100%',
            denominator=formula,
            answer=((current_a - current_b) / base_diff - 1) * 100,
            digits=1,
            unit='%',
            hint='差值增长率 = (现期差 - 基期差) / 基期差',
            operands=operands,
        )

    def interval_growth_rate(self) -> DataPracticeQuestion:
        first, second = self.random.rate(5, 30), self.random.rate(5, 30)
        return self.result(
            material=f'{self.year}年，{self.region}{self.indicator}同比增长{number_text(first)}%；'
            f'{self.year - 1}年同比增长{number_text(second)}%。',
            question=f'{self.year}年相比{self.year - 2}年的增长率约为多少？',
            numerator=(
                f'{number_text(first)}% + {number_text(second)}% + {number_text(first)}% × {number_text(second)}%'
            ),
            answer=first + second + first * second / 100,
            digits=1,
            unit='%',
            hint='间隔增长率 = r₁ + r₂ + r₁×r₂',
            operands={'rate_a': first, 'rate_b': second},
        )

    def avg_growth_rate(self) -> DataPracticeQuestion:
        r = self.random
        total, count = r.value(5000, 90000), r.value(100, 5000)
        value_rate, count_rate = r.rate(5, 30), r.rate(3, 20)
        return self.result(
            material=f'{self.year}年，某行业总产值{total}亿元，同比增长{number_text(value_rate)}%；'
            f'从业人数{count}万人，同比增长{number_text(count_rate)}%。',
            question='该行业人均产值的同比增长率约为多少？',
            numerator=f'{number_text(value_rate)}% - {number_text(count_rate)}%',
            denominator=f'1 + {number_text(count_rate)}%',
            answer=(value_rate - count_rate) / (1 + count_rate / 100),
            digits=1,
            unit='%',
            hint='平均数增长率 = (总量增长率 - 份数增长率) / (1 + 份数增长率)',
            operands={'value_rate': value_rate, 'count_rate': count_rate, 'total': total, 'count': count},
        )

    def mixed_growth_rate(self) -> DataPracticeQuestion:
        r = self.random
        current_a, current_b = r.value(3000, 30000), r.value(2000, 20000)
        rate_a, rate_b = r.rate(5, 30), r.rate(5, 30)
        base = current_a / (1 + rate_a / 100) + current_b / (1 + rate_b / 100)
        formula = f'{current_a}/(1+{number_text(rate_a)}%) + {current_b}/(1+{number_text(rate_b)}%)'
        return self.result(
            material=f'{self.year}年，{self.region}A产业产值{current_a}亿元，同比增长{number_text(rate_a)}%；'
            f'B产业产值{current_b}亿元，同比增长{number_text(rate_b)}%。',
            question='A、B两产业合计产值的同比增长率约为多少？',
            numerator=f'({current_a + current_b} - ({formula})) × 100%',
            denominator=formula,
            answer=((current_a + current_b) / base - 1) * 100,
            digits=1,
            unit='%',
            hint='混合增长率 = 总增量 / 总基期量；权重应使用基期量',
            operands={'current_a': current_a, 'current_b': current_b, 'rate_a': rate_a, 'rate_b': rate_b},
        )

    def proportions(self) -> DataPracticeQuestion:
        r = self.random
        use_bias = self.key != 'proportion_diff'
        whole = r.value(10000, 99999)
        whole_rate, part_rate = r.rate(5, 25, use_bias=use_bias), r.rate(8, 35, use_bias=use_bias)
        part = integer(whole * r.rate(15, 55, use_bias=use_bias) / 100)
        part = min(part, int(whole * (1 + part_rate / 100) / (1 + whole_rate / 100) * 0.95))
        current_pct = part / whole * 100
        base_pct = current_pct * (1 + whole_rate / 100) / (1 + part_rate / 100)
        material = (
            f'{self.year}年{self.period}，某市生产总值{whole}亿元，同比增长{number_text(whole_rate)}%。'
            f'其中第三产业产值{part}亿元，同比增长{number_text(part_rate)}%。'
        )
        operands = {'whole': whole, 'part': part, 'whole_rate': whole_rate, 'part_rate': part_rate}
        if self.key == 'current_proportion':
            return self.result(
                material=material,
                question='本期第三产业产值占生产总值的比重约为多少？',
                numerator=f'{part} × 100%',
                denominator=str(whole),
                answer=current_pct,
                digits=1,
                unit='%',
                hint='本期比重 = 部分 / 整体',
                operands=operands,
            )
        if self.key == 'base_proportion':
            return self.result(
                material=material,
                question='上年同期第三产业产值占生产总值的比重约为多少？',
                numerator=f'{part}/(1+{number_text(part_rate)}%) × 100%',
                denominator=f'{whole}/(1+{number_text(whole_rate)}%)',
                answer=base_pct,
                digits=1,
                unit='%',
                hint='基期比重 = [部分现期/(1+部分增长率)] / [整体现期/(1+整体增长率)]',
                operands=operands,
            )
        return self.result(
            material=material,
            question='第三产业产值占比比上年同期变化多少个百分点（增加为正，减少为负）？',
            numerator=(
                f'({part}/{whole} - ({part}/{whole})'
                f' × (1+{number_text(whole_rate)}%)/(1+{number_text(part_rate)}%)) × 100'
            ),
            answer=current_pct - base_pct,
            digits=1,
            unit='个百分点',
            hint='两期比重差 = 本期比重 - 基期比重',
            operands=operands,
        )

    def partial_value(self) -> DataPracticeQuestion:
        whole, pct = self.random.value(10000, 99999), self.random.rate(10, 60)
        return self.result(
            material=f'{self.year}年{self.period}，{self.region}{self.indicator}为{whole}{self.unit}，某部分占比{number_text(pct)}%。',
            question=f'该部分的值约为多少{self.unit}？',
            numerator=f'{whole} × {number_text(pct)}%',
            answer=whole * pct / 100,
            unit=self.unit,
            hint='部分量 = 整体 × 比重',
            operands={'whole': whole, 'pct': pct},
        )

    def average_value(self) -> DataPracticeQuestion:
        total, count = self.random.value(5000, 90000), self.random.value(10, 500)
        return self.result(
            material=f'{self.year}年，{self.region}{self.indicator}总量{total}{self.unit}，共有{count}个统计单位。',
            question=f'平均每个单位的{self.indicator}为多少{self.unit}？',
            numerator=str(total),
            denominator=str(count),
            answer=total / count,
            digits=1,
            unit=self.unit,
            hint='平均值 = 总量 / 份数',
            operands={'total': total, 'count': count},
        )

    def growth_contribution(self) -> DataPracticeQuestion:
        whole, rate = self.random.value(20000, 90000), self.random.rate(8, 25)
        growth = whole - whole / (1 + rate / 100)
        part_growth = integer(growth * self.random.rate(20, 70) / 100)
        return self.result(
            material=f'{self.year}年，{self.region}{self.indicator}总量{whole}{self.unit}，同比增长{number_text(rate)}%。'
            f'其中某部分比上年同期增加{part_growth}{self.unit}。',
            question=f'该部分对{self.indicator}增长的贡献率约为多少？',
            numerator=f'{part_growth} × 100%',
            denominator=f'{whole} - {whole}/(1+{number_text(rate)}%)',
            answer=part_growth / growth * 100,
            digits=1,
            unit='%',
            hint='增长贡献率 = 部分增量 / 整体增量 × 100%',
            operands={'whole': whole, 'rate': rate, 'part_growth': part_growth},
        )

    def pull_growth(self) -> DataPracticeQuestion:
        base, growth = self.random.value(20000, 80000), self.random.value(500, 5000)
        return self.result(
            material=f'{self.year - 1}年，{self.region}{self.indicator}总量{base}{self.unit}；'
            f'{self.year}年某部分较上年增加{growth}{self.unit}。',
            question=f'该部分拉动{self.region}{self.indicator}增长多少个百分点？',
            numerator=f'{growth} × 100',
            denominator=str(base),
            answer=growth / base * 100,
            digits=1,
            unit='个百分点',
            hint='拉动增长百分点 = 部分增量 / 整体基期值 × 100',
            operands={'base': base, 'growth': growth},
        )

    def annual_avg_rate(self) -> DataPracticeQuestion:
        r = self.random
        year, years = r.rng.choice((2015, 2016, 2017, 2018)), r.rng.randint(3, 6)
        base = r.value(1000, 20000)
        end = integer(base * (1 + r.rate(5, 25) / 100) ** years)
        return self.result(
            material=f'{year}年某指标为{base}亿元，{year + years}年为{end}亿元。',
            question=f'{year}～{year + years}年该指标的年均增长率最接近多少？',
            numerator=f'[({end}/{base})^(1/{years}) - 1] × 100%',
            answer=((end / base) ** (1 / years) - 1) * 100,
            digits=1,
            unit='%',
            hint='年均增长率 = (末期/基期)^(1/年数) - 1',
            operands={'base': base, 'end': end, 'years': years},
        )


def create_data_practice(random: CalculationRandom, key: PracticeType) -> DataPracticeQuestion:
    if key == 'random':
        candidates = [item[0] for item in PRACTICE_TYPES if item[0] != 'random']
        if random.bias in ('allocation', 'char_fraction'):
            candidates = ['base_value', 'growth_amount']
        elif random.bias != 'auto':
            candidates = [item[0] for item in PRACTICE_TYPES if item[0] != 'random' and item[2]]
        key = random.rng.choice(candidates)
    generator = DataPracticeGenerator(random, key)
    creators = {
        'base_value': generator.base_or_growth,
        'base_diff': generator.differences,
        'growth_amount': generator.base_or_growth,
        'growth_rate': generator.growth_rate,
        'interval_growth_rate': generator.interval_growth_rate,
        'avg_growth_rate': generator.avg_growth_rate,
        'mixed_growth_rate': generator.mixed_growth_rate,
        'diff_growth_rate': generator.differences,
        'annual_avg_rate': generator.annual_avg_rate,
        'current_proportion': generator.proportions,
        'base_proportion': generator.proportions,
        'proportion_diff': generator.proportions,
        'partial_value': generator.partial_value,
        'average_value': generator.average_value,
        'growth_contribution': generator.growth_contribution,
        'pull_growth': generator.pull_growth,
    }
    return creators[key]()
