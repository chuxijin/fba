from __future__ import annotations

import ast
import math
import operator
import random

from typing import TYPE_CHECKING, get_args

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.gongkao.api.v1.calculation_practice import router
from backend.app.gongkao.schema.calculation_practice import (
    MAX_SAFE_INTEGER,
    AdvancedMethod,
    AdvancedMode,
    BasicCustomConfig,
    BasicType,
    CalcDifficulty,
    CalcMethodBias,
    FillBlankType,
    GenerateAdvancedCalculationParam,
    GenerateBasicCalculationParam,
    GenerateDataPracticeParam,
    GenerateFillBlankParam,
    PracticeType,
)
from backend.app.gongkao.service.calculation_practice_service import calculation_practice_service as service

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.app.gongkao.schema.calculation_practice import AdvancedQuestion


def _calculate(expression: str) -> float:
    """独立解析题目中的算式校验答案，不执行任意 Python 表达式。"""
    operations: dict[type, Callable[[float, float], float]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp):
            return operations[type(node.op)](visit(node.left), visit(node.right))
        raise AssertionError(f'非法算式节点：{node}')

    return visit(ast.parse(expression, mode='eval').body)


@pytest.mark.parametrize('key', get_args(BasicType))
def test_basic_answers_match_displayed_expression(key: BasicType) -> None:
    batch = service.generate_basic(obj=GenerateBasicCalculationParam(type_key=key, count=100, seed=42))
    assert batch.count == len(batch.questions) == 100
    for question in batch.questions:
        expression = question.expression.replace('×', '*').replace('÷', '/').replace('^', '**').rstrip('=≈')
        if '□' in expression:
            left, right = expression.replace('□', str(question.answer)).split('=')
            assert _calculate(left) == pytest.approx(float(right), rel=0, abs=1e-9)
        elif key == 'estimate_mul':
            first, second = map(int, expression.split('*'))
            assert question.answer == ((first + 5) // 10 * 10) * ((second + 5) // 10 * 10)
        else:
            assert question.answer == pytest.approx(_calculate(expression), abs=0.005001)
        assert math.isfinite(question.answer)
        assert question.explanation


@pytest.mark.parametrize('digits', [1, 2, 3, 4])
@pytest.mark.parametrize('operator_value', ['+', '-', '×', '÷'])
def test_custom_digits_and_operators(digits: int, operator_value: str) -> None:
    config = BasicCustomConfig(first_digits=digits, second_mode='fixed', fixed_second=13, operators=[operator_value])
    batch = service.generate_basic(
        obj=GenerateBasicCalculationParam(type_key='custom', custom_config=config, count=30, seed=2),
    )
    for question in batch.questions:
        expression = question.expression.rstrip('=≈').replace('×', '*').replace('÷', '/')
        assert question.answer == pytest.approx(_calculate(expression), abs=0.005001)
        if operator_value == '÷':
            dividend, divisor = map(int, question.expression.rstrip('≈').split('÷'))
            assert len(str(dividend)) == digits
            assert divisor == 13
            assert dividend % divisor != 0


def test_custom_powers_stay_within_javascript_safe_integer() -> None:
    batch = service.generate_basic(
        obj=GenerateBasicCalculationParam(
            type_key='custom',
            custom_config=BasicCustomConfig(mode='power', first_digits=4, second_mode='fixed', fixed_second=4),
            count=100,
            seed=7,
        )
    )
    for question in batch.questions:
        base = int(question.expression.split('^')[0])
        assert 1000 <= base <= 9999
        assert question.answer == base**4
        assert question.answer <= MAX_SAFE_INTEGER


@pytest.mark.parametrize('difficulty', get_args(CalcDifficulty))
@pytest.mark.parametrize('bias', get_args(CalcMethodBias))
@pytest.mark.parametrize('key', get_args(FillBlankType))
def test_fill_blank_all_combinations(key: FillBlankType, difficulty: CalcDifficulty, bias: CalcMethodBias) -> None:
    batch = service.generate_fill_blank(
        obj=GenerateFillBlankParam(
            type_key=key,
            difficulty=difficulty,
            method_bias=bias,
            count=25,
            seed=5,
        )
    )
    for question in batch.questions:
        assert question.type_key == key
        assert math.isfinite(question.answer)
        assert question.explanation
        if question.question_type == 'compare':
            assert question.left_display is not None and question.right_display is not None
            values = []
            for fraction in (question.left_display, question.right_display):
                value = float(fraction.numerator) / float(fraction.denominator)
                if fraction.suffix:
                    value *= float(fraction.suffix.replace('×', '').replace('%', '')) / 100
                values.append(value)
            expected = 'equal' if abs(values[0] - values[1]) < 1e-9 else 'greater' if values[0] > values[1] else 'less'
            assert question.compare_answer == expected
        elif key in ('fraction_lt', 'fraction_gt'):
            fraction = question.left_display
            assert fraction is not None
            value = float(fraction.numerator) / float(fraction.denominator)
            assert (value < 1) == (key == 'fraction_lt')
            assert question.answer == pytest.approx(value, abs=0.000501 if key == 'fraction_lt' else 0.005001)
        elif key == 'base_ratio':
            assert 0 < question.answer <= 1
        elif key == 'growth_amount':
            current_text, rate_text = question.expression.split('  ')
            current, rate = float(current_text.split(':')[1]), float(rate_text.split(':')[1].rstrip('%'))
            assert rate > -100
            assert question.answer == pytest.approx(current * rate / (100 + rate), abs=0.500001)
            assert (question.answer_prefix == '-') == (rate < 0)


def _practice_value_answer(key: str, v: dict[str, float]) -> float:
    if key == 'base_value':
        return v['current'] / (1 + v['rate'] / 100)
    if key == 'growth_amount':
        return abs(v['current'] - v['current'] / (1 + v['rate'] / 100))
    if key == 'growth_rate':
        return (v['current'] / v['base'] - 1) * 100
    if key in ('base_diff', 'diff_growth_rate', 'mixed_growth_rate'):
        base_a = v['current_a'] / (1 + v['rate_a'] / 100)
        base_b = v['current_b'] / (1 + v['rate_b'] / 100)
        if key == 'base_diff':
            return base_a - base_b
        if key == 'mixed_growth_rate':
            return ((v['current_a'] + v['current_b']) / (base_a + base_b) - 1) * 100
        return ((v['current_a'] - v['current_b']) / (base_a - base_b) - 1) * 100
    if key == 'partial_value':
        return v['whole'] * v['pct'] / 100
    if key == 'average_value':
        return v['total'] / v['count']
    raise AssertionError(f'未覆盖的数值题型：{key}')


def _practice_answer(key: str, v: dict[str, float]) -> float:
    if key in {
        'base_value',
        'growth_amount',
        'growth_rate',
        'base_diff',
        'diff_growth_rate',
        'mixed_growth_rate',
        'partial_value',
        'average_value',
    }:
        return _practice_value_answer(key, v)
    if key == 'interval_growth_rate':
        return ((1 + v['rate_a'] / 100) * (1 + v['rate_b'] / 100) - 1) * 100
    if key == 'avg_growth_rate':
        return ((1 + v['value_rate'] / 100) / (1 + v['count_rate'] / 100) - 1) * 100
    if key == 'annual_avg_rate':
        return ((v['end'] / v['base']) ** (1 / v['years']) - 1) * 100
    if key in ('current_proportion', 'base_proportion', 'proportion_diff'):
        current = v['part'] / v['whole'] * 100
        base = current * (1 + v['whole_rate'] / 100) / (1 + v['part_rate'] / 100)
        assert 0 < current < 100 and 0 < base < 100
        return current if key == 'current_proportion' else base if key == 'base_proportion' else current - base
    if key == 'growth_contribution':
        return v['part_growth'] / (v['whole'] - v['whole'] / (1 + v['rate'] / 100)) * 100
    return v['growth'] / v['base'] * 100


@pytest.mark.parametrize('difficulty', get_args(CalcDifficulty))
@pytest.mark.parametrize('bias', get_args(CalcMethodBias))
@pytest.mark.parametrize('key', get_args(PracticeType))
def test_practice_answers_and_unique_options(
    key: PracticeType,
    difficulty: CalcDifficulty,
    bias: CalcMethodBias,
) -> None:
    batch = service.generate_data_practice(
        obj=GenerateDataPracticeParam(
            type_key=key,
            difficulty=difficulty,
            method_bias=bias,
            count=25,
            seed=23,
        )
    )
    integer_keys = {'base_value', 'base_diff', 'growth_amount', 'partial_value'}
    for question in batch.questions:
        assert question.type_key != 'random'
        assert len(question.options) == len(set(question.options)) == 4
        numeric_option = question.options[question.correct_index].removesuffix(question.answer_unit)
        assert float(numeric_option) == pytest.approx(question.answer, rel=0, abs=1e-9)
        assert question.answer == pytest.approx(
            _practice_answer(question.type_key, question.operands),
            abs=0.500001 if question.type_key in integer_keys else 0.050001,
        )
        if question.type_key == 'growth_contribution':
            assert str(int(question.operands['part_growth'])) in question.material
        assert question.material and question.formula_numerator and question.formula_hint


def test_declines_and_zero_answers_have_valid_options() -> None:
    declines = service.generate_data_practice(obj=GenerateDataPracticeParam(type_key='growth_rate', count=100, seed=1))
    assert any(question.answer < 0 for question in declines.questions)
    zero_seen = False
    for seed in range(10):
        batch = service.generate_data_practice(
            obj=GenerateDataPracticeParam(type_key='proportion_diff', count=100, seed=seed),
        )
        zero_seen |= any(question.answer == 0 for question in batch.questions)
        for question in batch.questions:
            assert len(set(question.options)) == 4
    assert zero_seen


def _assert_advanced_math(question: AdvancedQuestion) -> None:
    if question.method == 'scaling_div':
        assert question.correct_value == pytest.approx(question.numerator / question.denominator, abs=0.000501)
        assert question.correct_delta_num == pytest.approx(
            abs(question.delta_denominator) * question.numerator / question.denominator,
            abs=0.500001,
        )
    elif question.method == 'scaling_mul':
        assert question.correct_delta_b == pytest.approx(
            question.num_a * question.num_b / question.target_a - question.num_b,
            abs=0.050001,
        )
        if question.mode == 'question':
            expected = question.num_a * question.num_b / (100 if question.is_percent_b else 1)
            assert question.correct_value == pytest.approx(expected, abs=0.500001)
    elif question.method == 'allocation':
        assert question.base_answer + question.growth_answer == question.current_value
        assert question.base_answer == pytest.approx(
            question.current_value / (1 + question.rate_percent / 100),
            abs=0.500001,
        )
    elif question.method == 'char_fraction':
        exact = question.current_value * question.given_rate / (100 + question.given_rate)
        assert question.correct_answer == pytest.approx(exact, abs=0.500001)
        estimate = question.current_value / (question.fraction_denom + 1)
        assert abs(estimate - question.correct_answer) <= max(1, question.correct_answer * question.tolerance)
    elif question.method == 'difference':
        rates = [(item.current_value - item.base_value) / item.base_value for item in question.items]
        expected = max(rates) if question.ask_highest else min(rates)
        assert rates[question.correct_index] == expected
        assert rates.count(expected) == 1
    else:
        value = question.truncated_numerator / question.truncated_denominator
        assert question.bin_start <= value < question.bin_start + question.bin_size
        if question.mode == 'formula':
            assert abs(question.correct_value - value) < 1


@pytest.mark.parametrize('method', get_args(AdvancedMethod))
@pytest.mark.parametrize('mode', get_args(AdvancedMode))
def test_advanced_math_and_modes(method: AdvancedMethod, mode: AdvancedMode) -> None:
    batch = service.generate_advanced(
        obj=GenerateAdvancedCalculationParam(method=method, mode=mode, count=100, seed=35),
    )
    if method == 'mixed_speed':
        assert len({question.method for question in batch.questions}) == 6
    for question in batch.questions:
        assert question.mode == mode
        assert math.isfinite(question.correct_value)
        assert question.explanation
        if mode == 'question' or question.method == 'difference':
            assert len(question.options) == len({option.display for option in question.options}) == 4
            assert question.options[question.correct_index].value == question.correct_value
        else:
            assert question.options == [] and question.correct_index == -1
        _assert_advanced_math(question)


def test_seed_replay_does_not_depend_on_other_requests_or_global_random() -> None:
    global_state = random.getstate()
    param = GenerateAdvancedCalculationParam(method='mixed_speed', count=25, seed=0)
    first = service.generate_advanced(obj=param)
    service.generate_advanced(obj=GenerateAdvancedCalculationParam(method='mixed_speed', count=100))
    assert service.generate_advanced(obj=param) == first
    assert random.getstate() == global_state
    generated = service.generate_basic(obj=GenerateBasicCalculationParam())
    assert service.generate_basic(obj=GenerateBasicCalculationParam(seed=generated.seed)) == generated


@pytest.mark.parametrize(
    'payload',
    [
        {'count': 0},
        {'count': 101},
        {'count': 1.5},
        {'count': True},
        {'seed': -1},
        {'seed': MAX_SAFE_INTEGER + 1},
        {'type_key': 'typo'},
        {'custom_config': {}},
        {'type_key': 'custom', 'custom_config': {'operators': []}},
        {'type_key': 'custom', 'custom_config': {'rangeStart': 100, 'rangeEnd': 10}},
        {'type_key': 'custom', 'custom_config': {'fixedSecond': 0}},
        {'type_key': 'custom', 'custom_config': {'firstDigits': 5}},
        {'difficulty': 'ignored_field'},
    ],
)
def test_invalid_basic_requests_are_rejected(payload: dict) -> None:
    with pytest.raises(ValidationError):
        GenerateBasicCalculationParam.model_validate(payload)


def test_catalog_has_every_supported_type_and_legacy_basic_order() -> None:
    catalog = service.get_catalog()
    assert [item.key for item in catalog.basic_types] == list(get_args(BasicType))
    assert [item.type_index for item in catalog.basic_types] == list(range(18))
    assert {item.key for item in catalog.fill_blank_types} == set(get_args(FillBlankType))
    assert {item.key for item in catalog.practice_types} == set(get_args(PracticeType))
    assert {item.key for item in catalog.advanced_methods} == set(get_args(AdvancedMethod))


@pytest.fixture
def calculation_client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix='/api/v1/gk/calculation-practice')
    return TestClient(app)


@pytest.mark.parametrize(
    'endpoint,payload,camel_field',
    [
        ('basic', {'type_key': 'three_digit_div_one'}, 'relativeTolerance'),
        ('fill-blank', {'type_key': 'base_compare'}, 'compareAnswer'),
        ('data-practice', {'type_key': 'growth_contribution'}, 'correctIndex'),
        ('advanced', {'method': 'scaling_mul'}, 'correctDeltaB'),
    ],
)
def test_http_contract(calculation_client: TestClient, endpoint: str, payload: dict, camel_field: str) -> None:
    payload.update(count=3, seed=7)
    response = calculation_client.post(f'/api/v1/gk/calculation-practice/{endpoint}/generate', json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body['code'] == 200
    assert body['data']['count'] == 3
    assert body['data']['seed'] == 7
    assert camel_field in body['data']['questions'][0]
    assert body == calculation_client.post(f'/api/v1/gk/calculation-practice/{endpoint}/generate', json=payload).json()


def test_http_validation_and_openapi(calculation_client: TestClient) -> None:
    prefix = '/api/v1/gk/calculation-practice'
    assert calculation_client.get(f'{prefix}/catalog').status_code == 200
    assert calculation_client.post(f'{prefix}/advanced/generate', json={'method': 'unknown'}).status_code == 422
    assert calculation_client.post(f'{prefix}/fill-blank/generate', json={'difficulty': 'extreme'}).status_code == 422
    assert calculation_client.post(f'{prefix}/data-practice/generate', json={'count': 1000}).status_code == 422
    schema = calculation_client.get('/openapi.json').json()
    assert f'{prefix}/advanced/generate' in schema['paths']
    assert 'ScalingMulQuestion' in schema['components']['schemas']
