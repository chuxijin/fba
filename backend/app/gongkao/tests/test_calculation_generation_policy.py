import math

from typing import get_args

import pytest

from backend.app.gongkao.schema.calculation_practice import (
    CalcDifficulty,
    FillBlankType,
    GenerateAdvancedCalculationParam,
    GenerateDataPracticeParam,
    GenerateFillBlankParam,
)
from backend.app.gongkao.service.calculation.common import CalculationRandom, rounded
from backend.app.gongkao.service.calculation_practice_service import calculation_practice_service as service


@pytest.mark.parametrize('difficulty', get_args(CalcDifficulty))
@pytest.mark.parametrize('answer,digits', [(3127, 0), (-3127, 0), (13.1, 1), (-0.3, 1), (0, 1)])
def test_nearest_option_spacing(difficulty: CalcDifficulty, answer: float, digits: int) -> None:
    random = CalculationRandom(37, difficulty)
    for _ in range(100):
        values, index = random.options(answer, digits)
        assert len(set(values)) == 4
        assert values[index] == rounded(answer, digits)
        gap = min(abs(value - answer) for i, value in enumerate(values) if i != index)
        quantum = 10**-digits
        low, high = random.config.option_gap
        assert max(quantum, abs(answer) * low - quantum / 2) - 1e-9 <= gap
        assert gap <= max(quantum, abs(answer) * high + quantum / 2) + 1e-9


def test_natural_values_are_not_coupled_to_difficulty() -> None:
    samples = []
    for difficulty in get_args(CalcDifficulty):
        random = CalculationRandom(7, difficulty)
        values = [random.value(100, 99999) for _ in range(600)]
        assert {len(str(value)) for value in values} == {3, 4, 5}
        assert sum(value % 10 != 0 for value in values) > 500
        samples.append(values)
    assert samples[0] == samples[1] == samples[2]


def test_correct_option_can_be_smallest_or_largest_not_always_middle() -> None:
    random = CalculationRandom(93)
    ranks = set()
    for _ in range(100):
        values, index = random.options(1000)
        ranks.add(sorted(values).index(values[index]))
    assert ranks == {0, 1, 2, 3}


@pytest.mark.parametrize('key', get_args(FillBlankType))
def test_numeric_tolerance_is_five_percent_and_comparisons_are_exact(key: FillBlankType) -> None:
    for difficulty in get_args(CalcDifficulty):
        batch = service.generate_fill_blank(obj=GenerateFillBlankParam(type_key=key, difficulty=difficulty, seed=18))
        for question in batch.questions:
            assert question.tolerance == pytest.approx(0 if question.question_type == 'compare' else 0.05)
            if key == 'base_value':
                numerator, denominator = question.expression.rstrip('≈').split('/')
                assert question.answer == pytest.approx(float(numerator) / float(denominator), abs=1e-10)


@pytest.mark.parametrize('difficulty', get_args(CalcDifficulty))
def test_characteristic_fraction_is_perturbed_and_selects_correct_option(difficulty: CalcDifficulty) -> None:
    irregular = 0
    for seed in range(5):
        batch = service.generate_advanced(
            obj=GenerateAdvancedCalculationParam(
                method='char_fraction',
                mode='question',
                difficulty=difficulty,
                count=100,
                seed=seed,
            )
        )
        for question in batch.questions:
            assert question.method == 'char_fraction'
            assert question.given_rate != rounded(100 / question.fraction_denom, 1)
            estimate = question.current_value / (question.fraction_denom + 1)
            exact = question.current_value * question.given_rate / (100 + question.given_rate)
            assert abs(estimate / exact - 1) <= 0.05
            errors = [abs(estimate - option.value) for option in question.options]
            assert errors[question.correct_index] == min(errors)
            assert errors.count(min(errors)) == 1
            irregular += question.current_value % (question.fraction_denom + 1) != 0
    assert irregular > 300


def test_hard_growth_amount_allocation_checks_final_growth_not_only_base() -> None:
    batch = service.generate_data_practice(
        obj=GenerateDataPracticeParam(
            type_key='growth_amount',
            difficulty='hard',
            method_bias='allocation',
            count=100,
            seed=72,
        )
    )
    for question in batch.questions:
        current, r = question.operands['current'], question.operands['rate'] / 100
        exact_base = current / (1 + r)
        step = 10 ** max(1, math.floor(math.log10(exact_base)) - 1)
        assumed = math.floor(exact_base / step + 0.5) * step
        residual = current - assumed * (1 + r)
        estimate = current - (assumed + residual * (1 - r))
        assert abs(estimate / (current - exact_base) - 1) <= 0.01
        errors = [abs(estimate - float(value.removesuffix(question.answer_unit))) for value in question.options]
        assert errors[question.correct_index] == min(errors)
        assert '假设' not in question.material + question.question


@pytest.mark.parametrize('bias', ['allocation', 'char_fraction'])
def test_random_method_training_only_selects_supported_targets(bias: str) -> None:
    batch = service.generate_data_practice(obj=GenerateDataPracticeParam(method_bias=bias, count=100, seed=18))
    assert {question.type_key for question in batch.questions} == {'base_value', 'growth_amount'}
