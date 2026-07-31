import asyncio

from decimal import Decimal
from typing import Any

import pytest

from backend.plugin.render_book.schema.render import RenderJobCreate
from backend.plugin.render_book.service.v2_payload_service import V2RenderPayloadService


def test_v2_private_external_wrong_question_builds_render_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """用户导入的私有错题没有题库挂载，也必须能生成完整题本载荷。"""

    async def fake_load_questions(**_kwargs: Any) -> list[dict[str, Any]]:
        await asyncio.sleep(0)
        return [
            {
                'id': 101,
                'stem': '用户导入题干',
                'question_type': 'single_choice',
                'option_data': [
                    {'option_code': 'B', 'content': '错误选项', 'sort_order': 1},
                    {'option_code': 'A', 'content': '正确选项', 'sort_order': 0},
                ],
                'default_score': Decimal('1.00'),
                'difficulty': Decimal('3.00'),
                'answer_data': {'correct': 'A'},
                'explanation': '用户填写的解析',
            }
        ]

    async def fake_load_knowledge_points(**_kwargs: Any) -> dict[int, list[str]]:
        await asyncio.sleep(0)
        return {101: ['数量关系']}

    async def fake_load_contexts(**_kwargs: Any) -> dict[int, dict[str, Any]]:
        await asyncio.sleep(0)
        return {}

    async def fake_load_materials(**_kwargs: Any) -> tuple[dict[int, list[int]], list[Any]]:
        await asyncio.sleep(0)
        return {}, []

    monkeypatch.setattr(V2RenderPayloadService, '_load_questions', fake_load_questions)
    monkeypatch.setattr(V2RenderPayloadService, '_load_knowledge_points', fake_load_knowledge_points)
    monkeypatch.setattr(V2RenderPayloadService, '_load_contexts', fake_load_contexts)
    monkeypatch.setattr(V2RenderPayloadService, '_load_materials', fake_load_materials)

    payload = RenderJobCreate(
        template_key='wrong_question',
        title='我的错题本',
        filters={'question_ids': [101]},
        metadata={'user_id': 7, 'qbank_version': 'v2', 'source_type': 'wrong'},
    )
    result = asyncio.run(V2RenderPayloadService.build_payload(db=None, payload=payload))

    question = result.paper.sections[0].questions[0]
    assert result.paper.question_count == 1
    assert result.paper.material_count == 0
    assert question.question_id == 101
    assert [option.key for option in question.options] == ['A', 'B']
    assert question.answer_text == 'A'
    assert question.analysis_text == '用户填写的解析'
    assert question.knowledge_points == ['数量关系']
    assert question.bank_id is None
    assert result.metadata['question_ids'] == [101]
