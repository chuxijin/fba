import secrets

from backend.app.gongkao.schema.calculation_practice import (
    MAX_SAFE_INTEGER,
    AdvancedQuestion,
    BasicCalculationSession,
    BasicCustomConfig,
    CalculationCatalog,
    CalculationCatalogItem,
    CalculationSession,
    DataPracticeQuestion,
    FillBlankQuestion,
    GenerateAdvancedCalculationParam,
    GenerateBasicCalculationParam,
    GenerateDataPracticeParam,
    GenerateFillBlankParam,
)
from backend.app.gongkao.service.calculation.advanced import ADVANCED_METHODS, create_advanced
from backend.app.gongkao.service.calculation.basic import BASIC_TYPES, create_basic, get_thresholds
from backend.app.gongkao.service.calculation.common import GENERATOR_VERSION, CalculationRandom
from backend.app.gongkao.service.calculation.data_practice import PRACTICE_TYPES, create_data_practice
from backend.app.gongkao.service.calculation.fill_blank import FILL_BLANK_TYPES, create_fill_blank


def _seed(value: int | None) -> int:
    return value if value is not None else secrets.randbelow(MAX_SAFE_INTEGER + 1)


class CalculationPracticeService:
    """无数据库、HTTP 或用户会话依赖的计算练习服务，可供 API、Agent 和 skill 直接复用。"""

    @staticmethod
    def get_catalog() -> CalculationCatalog:
        return CalculationCatalog(
            generator_version=GENERATOR_VERSION,
            basic_types=[
                CalculationCatalogItem(key=key, title=title, hint=hint, type_index=index)
                for index, (key, title, hint, _) in enumerate(BASIC_TYPES)
            ],
            fill_blank_types=[
                CalculationCatalogItem(key=key, title=title, group=group, supports_method_bias=bias)
                for key, title, group, bias in FILL_BLANK_TYPES
            ],
            practice_types=[
                CalculationCatalogItem(key=key, title=title, supports_method_bias=bias)
                for key, title, bias in PRACTICE_TYPES
            ],
            advanced_methods=[CalculationCatalogItem(key=key, title=title) for key, title in ADVANCED_METHODS],
            difficulties=['easy', 'normal', 'hard'],
            method_biases=['auto', 'scaling_div', 'char_fraction', 'allocation'],
            advanced_modes=['formula', 'question'],
            default_custom_config=BasicCustomConfig(),
        )

    @staticmethod
    def generate_basic(*, obj: GenerateBasicCalculationParam) -> BasicCalculationSession:
        seed = _seed(obj.seed)
        random = CalculationRandom(seed)
        config = obj.custom_config or BasicCustomConfig()
        return BasicCalculationSession(
            generator_version=GENERATOR_VERSION,
            seed=seed,
            count=obj.count,
            type_key=obj.type_key,
            custom_config=config if obj.type_key == 'custom' else None,
            performance_thresholds=get_thresholds(obj.type_key, obj.count, config),
            questions=[create_basic(random.rng, obj.type_key, config) for _ in range(obj.count)],
        )

    @staticmethod
    def generate_fill_blank(*, obj: GenerateFillBlankParam) -> CalculationSession[FillBlankQuestion]:
        seed = _seed(obj.seed)
        random = CalculationRandom(seed, obj.difficulty, obj.method_bias)
        return CalculationSession[FillBlankQuestion](
            generator_version=GENERATOR_VERSION,
            seed=seed,
            count=obj.count,
            questions=[create_fill_blank(random, obj.type_key) for _ in range(obj.count)],
        )

    @staticmethod
    def generate_data_practice(*, obj: GenerateDataPracticeParam) -> CalculationSession[DataPracticeQuestion]:
        seed = _seed(obj.seed)
        random = CalculationRandom(seed, obj.difficulty, obj.method_bias)
        return CalculationSession[DataPracticeQuestion](
            generator_version=GENERATOR_VERSION,
            seed=seed,
            count=obj.count,
            questions=[create_data_practice(random, obj.type_key) for _ in range(obj.count)],
        )

    @staticmethod
    def generate_advanced(*, obj: GenerateAdvancedCalculationParam) -> CalculationSession[AdvancedQuestion]:
        seed = _seed(obj.seed)
        random = CalculationRandom(seed, obj.difficulty)
        return CalculationSession[AdvancedQuestion](
            generator_version=GENERATOR_VERSION,
            seed=seed,
            count=obj.count,
            questions=[create_advanced(random, obj.method, obj.mode) for _ in range(obj.count)],
        )


calculation_practice_service = CalculationPracticeService()
