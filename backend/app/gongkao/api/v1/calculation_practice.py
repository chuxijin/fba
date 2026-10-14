from fastapi import APIRouter

from backend.app.gongkao.schema.calculation_practice import (
    AdvancedQuestion,
    BasicCalculationSession,
    CalculationCatalog,
    CalculationSession,
    DataPracticeQuestion,
    FillBlankQuestion,
    GenerateAdvancedCalculationParam,
    GenerateBasicCalculationParam,
    GenerateDataPracticeParam,
    GenerateFillBlankParam,
)
from backend.app.gongkao.service.calculation_practice_service import calculation_practice_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base

router = APIRouter()


@router.get('/catalog', summary='获取计算练习题型与参数目录')
async def get_calculation_catalog() -> ResponseSchemaModel[CalculationCatalog]:
    return response_base.success(data=calculation_practice_service.get_catalog())


@router.post('/basic/generate', summary='生成基础计算题单', response_model_exclude_none=True)
def generate_basic_calculation(obj: GenerateBasicCalculationParam) -> ResponseSchemaModel[BasicCalculationSession]:
    return response_base.success(data=calculation_practice_service.generate_basic(obj=obj))


@router.post('/fill-blank/generate', summary='生成资料分析填空与比较题单', response_model_exclude_none=True)
def generate_fill_blank(obj: GenerateFillBlankParam) -> ResponseSchemaModel[CalculationSession[FillBlankQuestion]]:
    return response_base.success(data=calculation_practice_service.generate_fill_blank(obj=obj))


@router.post('/data-practice/generate', summary='生成资料分析实战选择题单')
def generate_data_practice(
    obj: GenerateDataPracticeParam,
) -> ResponseSchemaModel[CalculationSession[DataPracticeQuestion]]:
    return response_base.success(data=calculation_practice_service.generate_data_practice(obj=obj))


@router.post('/advanced/generate', summary='生成进阶计算题单')
def generate_advanced_calculation(
    obj: GenerateAdvancedCalculationParam,
) -> ResponseSchemaModel[CalculationSession[AdvancedQuestion]]:
    return response_base.success(data=calculation_practice_service.generate_advanced(obj=obj))
