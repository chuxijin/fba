from typing import Annotated, Generic, Literal, TypeVar

from pydantic import ConfigDict, Field, computed_field, model_validator
from pydantic.alias_generators import to_camel

from backend.app.gongkao.schema.calculation_contract import CalculationQuestionContract
from backend.common.schema import SchemaBase

CalcDifficulty = Literal['easy', 'normal', 'hard']
CalcMethodBias = Literal['auto', 'scaling_div', 'char_fraction', 'allocation']
BasicType = Literal[
    'two_digit_add_sub',
    'round_hundred',
    'three_digit_add',
    'three_digit_sub',
    'three_digit_add_sub',
    'multi_add',
    'mixed_add_sub',
    'two_digit_mul_one',
    'three_digit_mul_one',
    'mul_11',
    'mul_15',
    'two_digit_mul_two',
    'three_digit_div_one',
    'three_digit_div_two',
    'estimate_mul',
    'five_digit_div_three',
    'three_digit_div_four',
    'custom',
]
FillBlankType = Literal[
    'base_value',
    'growth_amount',
    'percent_convert',
    'growth_compare',
    'base_compare',
    'avg_growth_rate',
    'fraction_lt',
    'fraction_gt',
    'base_ratio',
    'fraction_compare',
    'yearly_average',
]
PracticeType = Literal[
    'random',
    'base_value',
    'base_diff',
    'growth_amount',
    'growth_rate',
    'interval_growth_rate',
    'avg_growth_rate',
    'mixed_growth_rate',
    'diff_growth_rate',
    'annual_avg_rate',
    'current_proportion',
    'base_proportion',
    'proportion_diff',
    'partial_value',
    'average_value',
    'growth_contribution',
    'pull_growth',
]
AdvancedMethod = Literal[
    'scaling_div',
    'scaling_mul',
    'allocation',
    'range_est',
    'char_fraction',
    'difference',
    'mixed_speed',
]
AdvancedMode = Literal['formula', 'question']
CompareAnswer = Literal['greater', 'less', 'equal']
Operator = Literal['+', '-', '×', '÷']
MAX_SAFE_INTEGER = 9007199254740991


class CalculationDisplaySchema(SchemaBase):
    """题目展示字段沿用小程序 camelCase，同时接受 Python snake_case 参数。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra='forbid', allow_inf_nan=False)


class BasicCustomConfig(CalculationDisplaySchema):
    mode: Literal['standard', 'power'] = Field(default='standard', description='标准四则运算或幂运算')
    first_digits: int = Field(default=2, ge=1, le=4, strict=True, description='第一个数的位数')
    operators: list[Operator] = Field(default_factory=lambda: ['+'], min_length=1, max_length=4, description='运算符')
    second_mode: Literal['random_digits', 'fixed', 'range'] = Field(default='random_digits', description='第二个数来源')
    second_digits: int = Field(default=2, ge=1, le=4, strict=True, description='第二个数的位数')
    fixed_second: int = Field(default=11, ge=1, le=999999, strict=True, description='固定的第二个数')
    range_start: int = Field(default=10, ge=1, le=999999, strict=True, description='第二个数范围下限')
    range_end: int = Field(default=99, ge=1, le=999999, strict=True, description='第二个数范围上限')

    @model_validator(mode='after')
    def validate_range(self) -> 'BasicCustomConfig':
        if self.range_start > self.range_end:
            raise ValueError('rangeStart 不能大于 rangeEnd')
        if len(set(self.operators)) != len(self.operators):
            raise ValueError('operators 不能包含重复运算符')
        return self


class GenerateCalculationParam(SchemaBase):
    model_config = ConfigDict(extra='forbid')

    count: int = Field(default=10, ge=1, le=100, strict=True, description='题量，1～100')
    seed: int | None = Field(
        default=None,
        ge=0,
        le=MAX_SAFE_INTEGER,
        strict=True,
        description='随机种子；相同版本、参数和种子可重现同一题单，省略时由服务端生成',
    )


class GenerateBasicCalculationParam(GenerateCalculationParam):
    type_key: BasicType = Field(default='two_digit_add_sub', description='基础计算题型，见 catalog')
    custom_config: BasicCustomConfig | None = Field(default=None, description='仅 custom 题型使用，省略时采用默认配置')

    @model_validator(mode='after')
    def validate_custom_config(self) -> 'GenerateBasicCalculationParam':
        if self.custom_config is not None and self.type_key != 'custom':
            raise ValueError('custom_config 仅适用于 custom 题型')
        return self


class GenerateDataAnalysisParam(GenerateCalculationParam):
    difficulty: CalcDifficulty = Field(default='normal', description='难度：easy / normal / hard')
    method_bias: CalcMethodBias = Field(default='auto', description='数字结构偏向；适用题型见 catalog')


class GenerateFillBlankParam(GenerateDataAnalysisParam):
    type_key: FillBlankType = Field(default='base_value', description='专项填空/比较题型')


class GenerateDataPracticeParam(GenerateDataAnalysisParam):
    type_key: PracticeType = Field(default='random', description='实战题型，random 表示随机混合')


class GenerateAdvancedCalculationParam(GenerateCalculationParam):
    difficulty: CalcDifficulty = Field(default='normal', description='数值选择题的选项间距难度')
    method: AdvancedMethod = Field(default='scaling_div', description='速算方法，mixed_speed 表示混合训练')
    mode: AdvancedMode = Field(default='formula', description='formula 直接公式 / question 文字应用')


class PerformanceThresholds(SchemaBase):
    excellent: int = Field(description='优秀的单题秒数上限')
    good: int = Field(description='良好的单题秒数上限')
    pass_seconds: int = Field(alias='pass', description='合格的单题秒数上限')


class CalculationQuestionBase(CalculationDisplaySchema):
    @computed_field
    @property
    def contract(self) -> CalculationQuestionContract:
        # 延迟导入避免 schema 与转换服务循环加载；不缓存，保证字段更新后协议同步。
        from backend.app.gongkao.service.calculation.contract import build_question_contract

        return build_question_contract(self)


class BasicCalculationQuestion(CalculationQuestionBase):
    expression: str = Field(description='可直接展示的算式')
    answer: int | float = Field(description='参考答案')
    relative_tolerance: float | None = Field(default=None, description='相对误差比例；空值表示精确作答')
    explanation: list[str] = Field(default_factory=list, description='计算说明')


class FractionDisplay(CalculationDisplaySchema):
    numerator: str = Field(description='分子展示文本')
    denominator: str = Field(description='分母展示文本')
    suffix: str | None = Field(default=None, description='分式后缀')


class FillBlankQuestion(CalculationQuestionBase):
    type_key: FillBlankType = Field(description='实际题型')
    question_type: Literal['input', 'compare'] = Field(default='input', description='数字输入或大小比较')
    display_mode: Literal['text', 'fraction', 'double_fraction', 'compare'] = Field(
        default='text',
        description='展示布局',
    )
    expression: str = Field(default='', description='文本算式')
    hint: str = Field(default='', description='题干提示')
    sub_hint: str | None = Field(default=None, description='补充提示')
    tolerance: float = Field(default=0, ge=0, description='相对容差；比较题为 0')
    answer: float = Field(default=0, description='数字参考答案；比较题使用 compareAnswer')
    answer_prefix: str | None = Field(default=None, description='输入前缀，例如下降量的负号')
    left_display: FractionDisplay | None = Field(default=None, description='左侧分式')
    right_display: FractionDisplay | None = Field(default=None, description='右侧分式')
    expression_suffix: str | None = Field(default=None, description='算式后缀')
    compare_answer: CompareAnswer | None = Field(default=None, description='大小比较的正确关系')
    explanation: list[str] = Field(default_factory=list, description='计算说明')


class DataPracticeQuestion(CalculationQuestionBase):
    type_key: PracticeType = Field(description='实际题型，随机题单中每道题单独标注')
    material: str = Field(description='完整文字材料')
    question: str = Field(description='问题')
    formula_numerator: str = Field(description='公式分子，或完整的非分式公式')
    formula_denominator: str = Field(default='', description='公式分母；非分式为空')
    options: list[str] = Field(min_length=4, max_length=4, description='四个不重复选项')
    correct_index: int = Field(ge=0, le=3, description='正确选项下标，从 0 开始')
    answer: float = Field(description='参考答案数值')
    answer_unit: str = Field(default='', description='答案单位，例如 %、个百分点、亿元')
    formula_hint: str = Field(description='公式与方法说明')
    operands: dict[str, float] = Field(description='题干中的结构化数值，供 Agent 等调用方复用')
    explanation: list[str] = Field(default_factory=list, description='计算说明')


class AdvancedOption(CalculationDisplaySchema):
    value: float = Field(description='选项数值')
    display: str = Field(description='选项展示文本')


class AdvancedQuestionBase(CalculationQuestionBase):
    mode: AdvancedMode = Field(description='训练呈现模式')
    material: str = Field(description='题目材料')
    question: str = Field(description='问题')
    answer_text: str = Field(description='可直接展示的参考答案')
    options: list[AdvancedOption] = Field(default_factory=list, description='选择题选项，输入题为空')
    correct_index: int = Field(default=-1, ge=-1, le=3, description='正确选项下标；输入题为 -1')
    correct_value: float = Field(description='参考数值；双空题还需 baseAnswer / growthAnswer')
    explanation: list[str] = Field(description='分步解题过程')


class ScalingDivQuestion(AdvancedQuestionBase):
    method: Literal['scaling_div'] = 'scaling_div'
    numerator: int = Field(description='原分子')
    denominator: int = Field(description='原分母')
    target_denominator: int = Field(description='目标分母')
    delta_denominator: int = Field(description='分母有符号改变量')
    correct_delta_num: float = Field(description='分子同步改变量的绝对值，不提前取整')
    tolerance: float = Field(default=0.05, description='相对数学真值的容差；零答案需精确作答')


class ScalingMulQuestion(AdvancedQuestionBase):
    method: Literal['scaling_mul'] = 'scaling_mul'
    num_a: int = Field(description='原因数 A')
    num_b: float = Field(description='原因数 B，百分比形式使用百分数数值')
    target_a: int = Field(description='目标因数 A')
    delta_a: int = Field(description='A 的有符号改变量')
    correct_delta_b: float = Field(description='保持乘积不变时 B 的有符号改变量')
    tolerance: float = Field(default=0.05, description='相对数学真值的容差；百分数与普通数统一规则')
    is_percent_b: bool = Field(description='B 是否为百分数；输入改变量的单位为百分点')


class AllocationQuestion(AdvancedQuestionBase):
    method: Literal['allocation'] = 'allocation'
    current_value: int = Field(description='现期值')
    rate_percent: float = Field(description='增长率百分数')
    assumed_base: int = Field(description='假设基期值')
    correction: int = Field(description='假设值的修正量')
    base_answer: int = Field(description='基期参考答案')
    growth_answer: int = Field(description='增长量参考答案')
    tolerance: float = Field(default=0.05, description='相对数学真值的容差；零答案需精确作答')


class RangeEstQuestion(AdvancedQuestionBase):
    method: Literal['range_est'] = 'range_est'
    numerator: int = Field(description='原分子')
    denominator: int = Field(description='原分母')
    truncated_numerator: int = Field(description='截位分子')
    truncated_denominator: int = Field(description='截位分母')
    estimate: float = Field(description='截位商')
    bin_size: int = Field(default=5, description='估值区间宽度')
    bin_start: int = Field(description='正确区间起点，左闭右开')


class CharFractionQuestion(AdvancedQuestionBase):
    method: Literal['char_fraction'] = 'char_fraction'
    current_value: int = Field(description='现期值')
    given_rate: float = Field(description='题干增长率百分数')
    exact_rate: float = Field(description='特征分数对应的百分数近似值')
    fraction_denom: int = Field(description='特征分数 1/n 的分母')
    correct_answer: int = Field(description='增长量参考答案')
    tolerance: float = Field(default=0.05, description='相对数学真值的容差；零答案需精确作答')


class DifferenceDataItem(CalculationDisplaySchema):
    label: str = Field(description='选项/地区标签')
    current_value: int = Field(description='现期值')
    base_value: int = Field(description='基期值')
    rate: float = Field(description='增长率小数')


class DifferenceQuestion(AdvancedQuestionBase):
    method: Literal['difference'] = 'difference'
    items: list[DifferenceDataItem] = Field(description='四组待比较数据')
    ask_highest: bool = Field(description='求最大值为 true，最小值为 false')
    correct_label: str = Field(description='正确标签')


AdvancedQuestion = Annotated[
    ScalingDivQuestion
    | ScalingMulQuestion
    | AllocationQuestion
    | RangeEstQuestion
    | CharFractionQuestion
    | DifferenceQuestion,
    Field(discriminator='method'),
]
QuestionT = TypeVar('QuestionT')


class CalculationSession(SchemaBase, Generic[QuestionT]):
    generator_version: str = Field(description='出题算法版本')
    seed: int = Field(description='本题单随机种子')
    count: int = Field(description='实际题量')
    questions: list[QuestionT] = Field(description='完整题单与答案')


class BasicCalculationSession(CalculationSession[BasicCalculationQuestion]):
    type_key: BasicType = Field(description='题型标识')
    custom_config: BasicCustomConfig | None = Field(default=None, description='实际使用的自定义配置')
    performance_thresholds: PerformanceThresholds = Field(description='单题耗时评价阈值')


class CalculationCatalogItem(SchemaBase):
    key: str = Field(description='稳定的题型/方法标识')
    title: str = Field(description='名称')
    hint: str = Field(default='', description='练习说明')
    group: str | None = Field(default=None, description='所属分组')
    type_index: int | None = Field(default=None, description='兼容旧基础计算页面的索引')
    supports_method_bias: bool = Field(default=False, description='是否支持方法偏向')


class CalculationCatalog(SchemaBase):
    generator_version: str = Field(description='出题算法版本')
    max_count: int = Field(default=100, description='每次生成题量上限')
    basic_types: list[CalculationCatalogItem] = Field(description='基础计算题型')
    fill_blank_types: list[CalculationCatalogItem] = Field(description='专项填空/比较题型')
    practice_types: list[CalculationCatalogItem] = Field(description='专项实战题型')
    advanced_methods: list[CalculationCatalogItem] = Field(description='进阶算法')
    difficulties: list[CalcDifficulty] = Field(description='难度枚举')
    method_biases: list[CalcMethodBias] = Field(description='方法偏向枚举')
    advanced_modes: list[AdvancedMode] = Field(description='进阶呈现模式')
    default_custom_config: BasicCustomConfig = Field(description='基础计算默认自定义参数')
