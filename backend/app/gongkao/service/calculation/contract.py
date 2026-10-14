from backend.app.gongkao.schema.calculation_contract import (
    CalculationQuestionContract,
    ChoiceOption,
    ChoiceResponse,
    ComparisonResponse,
    NumericAnswerField,
    NumericResponse,
    QuestionDisplay,
)
from backend.app.gongkao.schema.calculation_practice import (
    AdvancedQuestionBase,
    AllocationQuestion,
    BasicCalculationQuestion,
    CalculationQuestionBase,
    CharFractionQuestion,
    DataPracticeQuestion,
    FillBlankQuestion,
    RangeEstQuestion,
    ScalingDivQuestion,
    ScalingMulQuestion,
)
from backend.app.gongkao.service.calculation.common import number_text, rounded


def _field(
    value: float,
    *,
    field_id: str = 'answer',
    label: str = '答案',
    unit: str = '',
    tolerance: float | None = 0.05,
) -> NumericAnswerField:
    return NumericAnswerField(
        id=field_id,
        label=label,
        value=value,
        display=number_text(rounded(value, 6)),
        unit=unit,
        rule='exact' if tolerance is None or tolerance == 0 else 'relative',
        tolerance=tolerance or 0,
    )


def _choices(displays: list[str], index: int) -> ChoiceResponse:
    options = [ChoiceOption(id=f'option-{i + 1}', display=text) for i, text in enumerate(displays)]
    return ChoiceResponse(options=options, correct_option_id=options[index].id)


def _advanced_response(question: AdvancedQuestionBase) -> NumericResponse | ChoiceResponse:
    if question.options:
        return _choices([option.display for option in question.options], question.correct_index)
    # 在服务端统一产出真值，客户端不再按速算方法重算公式。
    if isinstance(question, ScalingDivQuestion):
        fields = [_field(question.correct_delta_num, label='分子改变量', tolerance=question.tolerance)]
    elif isinstance(question, ScalingMulQuestion):
        fields = [
            _field(
                question.correct_delta_b,
                label='因数 B 改变量',
                unit='percentagePoint' if question.is_percent_b else '',
                tolerance=question.tolerance,
            )
        ]
    elif isinstance(question, AllocationQuestion):
        base = question.current_value / (1 + question.rate_percent / 100)
        fields = [
            _field(base, field_id='base', label='基期', tolerance=question.tolerance),
            _field(question.current_value - base, field_id='growth', label='变化量', tolerance=question.tolerance),
        ]
    elif isinstance(question, CharFractionQuestion):
        exact = question.current_value * question.given_rate / (100 + question.given_rate)
        fields = [_field(exact, label='增长量', tolerance=question.tolerance)]
    elif isinstance(question, RangeEstQuestion):
        fields = [_field(question.correct_value, label='前两位', tolerance=None)]
    else:
        raise TypeError('缺少作答协议的进阶题型')
    return NumericResponse(fields=fields)


def build_question_contract(
    question: CalculationQuestionBase,
) -> CalculationQuestionContract:
    """兼容字段到统一协议的唯一出口；展示字段仍供旧版页面与专用组件使用。"""
    if isinstance(question, BasicCalculationQuestion):
        return CalculationQuestionContract(
            display=QuestionDisplay(expression=question.expression),
            response=NumericResponse(fields=[_field(question.answer, tolerance=question.relative_tolerance)]),
        )
    if isinstance(question, FillBlankQuestion):
        if question.question_type == 'compare' and question.compare_answer is None:
            raise ValueError('比较题缺少标准答案')
        unit = 'percent' if question.type_key in ('percent_convert', 'avg_growth_rate') else ''
        response = (
            ComparisonResponse(expected=question.compare_answer)
            if question.question_type == 'compare'
            else NumericResponse(fields=[_field(question.answer, unit=unit, tolerance=question.tolerance)])
        )
        expression = question.expression
        if question.left_display:
            left = question.left_display
            expression = f'({left.numerator}/{left.denominator}){left.suffix or ""}'
            if question.right_display:
                right = question.right_display
                operator = ' ? ' if question.question_type == 'compare' else ' × '
                expression += f'{operator}({right.numerator}/{right.denominator}){right.suffix or ""}'
            expression += question.expression_suffix or ''
        return CalculationQuestionContract(
            display=QuestionDisplay(prompt=question.hint, expression=expression, mode=question.display_mode),
            response=response,
        )
    if isinstance(question, DataPracticeQuestion):
        return CalculationQuestionContract(
            display=QuestionDisplay(
                material=question.material,
                prompt=question.question,
                expression=f'({question.formula_numerator}) / ({question.formula_denominator})'
                if question.formula_denominator
                else question.formula_numerator,
            ),
            response=_choices(question.options, question.correct_index),
        )
    if not isinstance(question, AdvancedQuestionBase):
        raise TypeError('不支持的计算题型')
    return CalculationQuestionContract(
        display=QuestionDisplay(material=question.material, prompt=question.question, mode=question.mode),
        response=_advanced_response(question),
    )
