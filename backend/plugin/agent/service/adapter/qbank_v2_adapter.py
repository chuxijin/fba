from __future__ import annotations

import re

from dataclasses import dataclass
from html import unescape
from typing import TYPE_CHECKING, Any

from backend.app.question_bank_v2.crud.crud_evaluation import EvaluationAttemptContext, evaluation_run_dao
from backend.app.question_bank_v2.crud.crud_material import question_material_dao
from backend.app.question_bank_v2.crud.crud_question import question_explanation_dao

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ShenlunAttemptInput:
    """申论批改工作流的只读输入快照"""

    context: EvaluationAttemptContext
    materials: list[dict[str, Any]]
    explanations: list[str]
    reference_context: dict[str, Any]

    @property
    def answer_text(self) -> str:
        return self.stringify(self.context.attempt.response_data)

    @staticmethod
    def stringify(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if value is None:
            return ''
        if isinstance(value, (dict, list)):
            import json

            return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        return str(value).strip()


class QbankV2Adapter:
    """从题库 V2 读取申论批改输入"""

    @staticmethod
    def clean(value: str | None) -> str:
        text = value or ''
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        return re.sub(r'\s+', ' ', unescape(text)).strip()

    async def get_attempt_input(self, *, db: AsyncSession, attempt_id: int, user_id: int) -> ShenlunAttemptInput:
        context = await evaluation_run_dao.get_attempt_context(
            db,
            attempt_id=attempt_id,
            user_id=user_id,
            for_update=False,
        )
        if context is None:
            raise ValueError('作答记录不存在或不属于当前用户')

        materials = await question_material_dao.get_all_by_questions(db, [context.question.id])
        material_payload = [
            {
                'material_number': index,
                'title': str(item.get('title') or ''),
                'content': self.clean(str(item.get('content') or '')),
                'role': str(item.get('role') or 'passage'),
            }
            for index, item in enumerate(materials, start=1)
        ]
        explanations = await question_explanation_dao.get_all(db, context.question.id)
        explanation_texts = [
            self.clean(item.content) for item in explanations if item.status == 'published' and item.content
        ]
        answer_data = dict(context.answer.answer_data or {})
        grading_config = dict(context.answer.grading_config or {})
        return ShenlunAttemptInput(
            context=context,
            materials=material_payload,
            explanations=explanation_texts,
            reference_context={
                'answer_data': answer_data,
                'grading_config': grading_config,
                'explanations': explanation_texts,
            },
        )


qbank_v2_adapter = QbankV2Adapter()
