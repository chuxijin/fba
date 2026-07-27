from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True, slots=True)
class PracticeGradeResult:
    """一次同步判分结果"""

    is_correct: bool | None
    score: Decimal | None
    grading_status: str
    grading_method: str
    details: dict[str, Any]


class PracticeGradingService:
    """题库 V2 同步判分服务类"""

    @staticmethod
    def _response_value(response_data: Any) -> Any:
        """兼容直接值和 {answer: ...} 两种客户端答案格式"""
        if isinstance(response_data, dict) and 'answer' in response_data:
            return response_data['answer']
        return response_data

    @staticmethod
    def _normalise_value(value: Any, *, case_sensitive: bool) -> Any:
        """规范化可自动判分的标量或列表"""
        if isinstance(value, str):
            value = value.strip()
            return value if case_sensitive else value.casefold()
        if isinstance(value, list):
            return [PracticeGradingService._normalise_value(item, case_sensitive=case_sensitive) for item in value]
        return value

    @staticmethod
    def _grade_range(*, response_value: Any, correct_value: Any, answer_data: dict[str, Any]) -> bool:
        """判定数值范围答案"""
        range_data = correct_value if isinstance(correct_value, dict) else answer_data
        try:
            numeric_value = Decimal(str(response_value))
            minimum = Decimal(str(range_data['min']))
            maximum = Decimal(str(range_data['max']))
        except (InvalidOperation, KeyError, TypeError, ValueError):
            return False
        else:
            return minimum <= numeric_value <= maximum

    @staticmethod
    def _grade_keywords(
        *,
        response_value: Any,
        correct_value: Any,
        grading_config: dict[str, Any],
        case_sensitive: bool,
    ) -> bool:
        """判定关键词答案"""
        keywords = grading_config.get('keywords', correct_value)
        if isinstance(keywords, str):
            keywords = [keywords]
        if not isinstance(response_value, str) or not isinstance(keywords, list):
            return False
        normalised_keywords = [
            PracticeGradingService._normalise_value(item, case_sensitive=case_sensitive) for item in keywords
        ]
        if not normalised_keywords:
            return False
        matches = sum(str(keyword) in response_value for keyword in normalised_keywords)
        try:
            required_matches = max(
                1,
                int(grading_config.get('min_matches', len(normalised_keywords))),
            )
        except (TypeError, ValueError):
            required_matches = len(normalised_keywords)
        return matches >= required_matches

    @staticmethod
    def _is_objective_response_correct(
        *,
        method: str,
        response_value: Any,
        correct_value: Any,
        answer_data: dict[str, Any],
        grading_config: dict[str, Any],
        case_sensitive: bool,
    ) -> bool:
        """按内置客观题方法判断答案是否正确"""
        if method == 'set':
            if not isinstance(response_value, list) or not isinstance(correct_value, list):
                return False
            try:
                return set(response_value) == set(correct_value)
            except TypeError:
                return False
        if method == 'ordered':
            return isinstance(response_value, list) and response_value == correct_value
        if method == 'range':
            return PracticeGradingService._grade_range(
                response_value=response_value,
                correct_value=correct_value,
                answer_data=answer_data,
            )
        if method == 'keyword':
            return PracticeGradingService._grade_keywords(
                response_value=response_value,
                correct_value=correct_value,
                grading_config=grading_config,
                case_sensitive=case_sensitive,
            )
        return response_value == correct_value

    @staticmethod
    def grade(
        *,
        response_data: Any,
        answer_data: dict[str, Any],
        grading_method: str,
        grading_config: dict[str, Any],
        question_type: str,
        max_score: Decimal,
    ) -> PracticeGradeResult:
        """执行内置客观题判分；主观题保留待评估状态"""
        if grading_method in {'manual', 'rubric', 'custom'}:
            return PracticeGradeResult(
                is_correct=None,
                score=None,
                grading_status='pending',
                grading_method='manual',
                details={'answer_grading_method': grading_method},
            )

        response_value = PracticeGradingService._response_value(response_data)
        correct_value = answer_data.get('correct')
        case_sensitive = bool(grading_config.get('case_sensitive'))
        response_value = PracticeGradingService._normalise_value(response_value, case_sensitive=case_sensitive)
        correct_value = PracticeGradingService._normalise_value(correct_value, case_sensitive=case_sensitive)
        method = 'set' if question_type == 'multiple_choice' else grading_method
        is_correct = PracticeGradingService._is_objective_response_correct(
            method=method,
            response_value=response_value,
            correct_value=correct_value,
            answer_data=answer_data,
            grading_config=grading_config,
            case_sensitive=case_sensitive,
        )
        return PracticeGradeResult(
            is_correct=is_correct,
            score=max_score if is_correct else Decimal(0),
            grading_status='graded',
            grading_method='rule',
            details={'answer_grading_method': method},
        )


practice_grading_service: PracticeGradingService = PracticeGradingService()
