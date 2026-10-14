from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class ContractModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra='forbid', allow_inf_nan=False)


class NumericAnswerField(ContractModel):
    id: str
    label: str
    value: float = Field(description='判题真值，不从 display 反解析')
    display: str = Field(description='参考答案展示文本，可以适当舍入')
    unit: str = Field(default='', description='percent 的数值使用 13.1 而不是 0.131；百分点为 percentagePoint')
    rule: Literal['exact', 'relative'] = 'relative'
    tolerance: float = Field(default=0.05, ge=0, le=1)

    @model_validator(mode='after')
    def validate_rule(self) -> 'NumericAnswerField':
        if self.rule == 'exact' and self.tolerance != 0:
            raise ValueError('精确判题的 tolerance 必须为 0')
        return self


class NumericResponse(ContractModel):
    kind: Literal['numeric'] = 'numeric'
    fields: list[NumericAnswerField] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_ids(self) -> 'NumericResponse':
        if len({field.id for field in self.fields}) != len(self.fields):
            raise ValueError('答案项 id 不能重复')
        return self


class ChoiceOption(ContractModel):
    id: str = Field(description='本题内稳定的选项 ID，与 A/B/C/D 展示序号分离')
    display: str


class ChoiceResponse(ContractModel):
    kind: Literal['singleChoice'] = 'singleChoice'
    options: list[ChoiceOption] = Field(min_length=2)
    correct_option_id: str

    @model_validator(mode='after')
    def validate_options(self) -> 'ChoiceResponse':
        ids = [option.id for option in self.options]
        if len(set(ids)) != len(ids) or self.correct_option_id not in ids:
            raise ValueError('选项 ID 必须唯一且包含正确选项')
        return self


class ComparisonResponse(ContractModel):
    kind: Literal['comparison'] = 'comparison'
    expected: Literal['greater', 'less', 'equal']


class QuestionDisplay(ContractModel):
    material: str = ''
    prompt: str = ''
    expression: str = ''
    mode: str = Field(default='text', description='仅用于展示；不决定判题方式')


class CalculationQuestionContract(ContractModel):
    version: Literal['1.0'] = '1.0'
    display: QuestionDisplay
    response: Annotated[NumericResponse | ChoiceResponse | ComparisonResponse, Field(discriminator='kind')]
