from typing import get_args

import pytest

from pydantic import ValidationError

from backend.app.gongkao.schema.calculation_contract import CalculationQuestionContract, ChoiceResponse, NumericResponse
from backend.app.gongkao.schema.calculation_practice import (
    AdvancedMethod,
    AdvancedMode,
    BasicType,
    CalculationSession,
    FillBlankType,
    GenerateAdvancedCalculationParam,
    GenerateBasicCalculationParam,
    GenerateDataPracticeParam,
    GenerateFillBlankParam,
    PracticeType,
)
from backend.app.gongkao.service.calculation_practice_service import calculation_practice_service as service


def check_batch(batch: CalculationSession) -> None:
    for question in batch.questions:
        contract = question.model_dump(by_alias=True)['contract']
        parsed = CalculationQuestionContract.model_validate(contract)
        assert parsed.version == '1.0'
        response = parsed.response
        if isinstance(response, NumericResponse):
            for field in response.fields:
                if field.rule == 'relative':
                    assert float(field.display) == pytest.approx(field.value, rel=field.tolerance, abs=0)
                else:
                    assert float(field.display) == pytest.approx(field.value, rel=0, abs=0)
        elif isinstance(response, ChoiceResponse):
            assert response.options[question.correct_index].id == response.correct_option_id
        else:
            assert response.expected == question.compare_answer


@pytest.mark.parametrize('key', get_args(BasicType))
def test_basic_contract(key: str) -> None:
    check_batch(service.generate_basic(obj=GenerateBasicCalculationParam(type_key=key, count=10, seed=11)))


@pytest.mark.parametrize('key', get_args(FillBlankType))
def test_fill_contract(key: str) -> None:
    check_batch(service.generate_fill_blank(obj=GenerateFillBlankParam(type_key=key, count=10, seed=11)))


@pytest.mark.parametrize('key', get_args(PracticeType))
def test_practice_contract(key: str) -> None:
    check_batch(service.generate_data_practice(obj=GenerateDataPracticeParam(type_key=key, count=10, seed=11)))


@pytest.mark.parametrize('method', get_args(AdvancedMethod))
@pytest.mark.parametrize('mode', get_args(AdvancedMode))
def test_advanced_contract(method: str, mode: str) -> None:
    batch = service.generate_advanced(obj=GenerateAdvancedCalculationParam(method=method, mode=mode, count=10, seed=11))
    check_batch(batch)
    for question in batch.questions:
        response = question.contract.response
        if isinstance(response, NumericResponse) and method == 'allocation':
            fields = {field.id: field.value for field in response.fields}
            assert fields['base'] == pytest.approx(question.current_value / (1 + question.rate_percent / 100))
            assert fields['base'] + fields['growth'] == pytest.approx(question.current_value)
        if isinstance(response, NumericResponse) and method == 'char_fraction':
            assert response.fields[0].value == pytest.approx(
                question.current_value * question.given_rate / (100 + question.given_rate)
            )


def test_invalid_contract_rejected() -> None:
    with pytest.raises(ValidationError):
        ChoiceResponse(options=[{'id': 'x', 'display': '1'}, {'id': 'y', 'display': '2'}], correct_option_id='z')
    field = {'id': 'x', 'label': '答案', 'value': 1, 'display': '1'}
    with pytest.raises(ValidationError):
        NumericResponse(fields=[field, field])
    with pytest.raises(ValidationError):
        NumericResponse(fields=[{**field, 'rule': 'exact', 'tolerance': 0.05}])
    with pytest.raises(ValidationError):
        NumericResponse(fields=[{**field, 'value': float('inf')}])
