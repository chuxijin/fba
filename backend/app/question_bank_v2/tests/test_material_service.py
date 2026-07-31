import asyncio
import importlib

from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any, TypeVar

import pytest

from pydantic import ValidationError
from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.schema.material import GetMaterialRevisionDetail, QuestionMaterialParam
from backend.app.question_bank_v2.schema.question import CreateQuestionParam
from backend.app.question_bank_v2.service.material_service import material_service
from backend.app.question_bank_v2.service.practice_service import PracticeService
from backend.common.exception import errors

material_service_module = importlib.import_module('backend.app.question_bank_v2.service.material_service')
T = TypeVar('T')


def run(coro: Coroutine[Any, Any, T]) -> T:
    """同步执行协程"""
    return asyncio.new_event_loop().run_until_complete(coro)


def test_question_revision_rejects_duplicate_material_role() -> None:
    """同一材料不能以相同用途重复关联到同一题目"""
    with pytest.raises(ValidationError, match='不能以相同用途重复关联同一材料'):
        CreateQuestionParam(
            code='TEST_001',
            stem='题干',
            question_type='single_choice',
            options=[
                {'option_code': 'A', 'content': 'A'},
                {'option_code': 'B', 'content': 'B'},
            ],
            answer={'answer_data': {'correct': 'A'}},
            explanations=[{'content': '解析', 'is_default': True}],
            materials=[
                {'material_id': 1, 'material_revision_id': 10, 'role': 'passage'},
                {'material_id': 1, 'material_revision_id': 11, 'role': 'passage'},
            ],
        )


def test_material_content_hash_is_stable_for_structured_data_order() -> None:
    """结构化数据键顺序不应影响材料内容哈希"""
    now = datetime.now(UTC)
    common = {
        'id': 10,
        'material_id': 1,
        'revision_no': 1,
        'title': '阅读材料',
        'content': '<p>正文</p>',
        'content_format': 'html',
        'source_name': None,
        'source_url': None,
        'content_hash': None,
        'status': 'draft',
        'published_by': None,
        'published_time': None,
        'created_by': 1,
        'updated_by': None,
        'created_time': now,
        'updated_time': None,
    }
    first = GetMaterialRevisionDetail(**common, structured_data={'page': 1, 'blocks': [{'id': 'a'}]})
    second = GetMaterialRevisionDetail(**common, structured_data={'blocks': [{'id': 'a'}], 'page': 1})

    assert material_service._content_hash(first) == material_service._content_hash(second)


def test_practice_delivery_deduplicates_shared_material_content() -> None:
    """多道题共享材料时正文只在会话材料目录中返回一次"""
    items = [{'question_id': 101}, {'question_id': 102}]
    common = {
        'material_id': 1,
        'material_revision_id': 10,
        'title': '共享阅读材料',
        'content': '正文',
        'content_format': 'plain',
        'structured_data': {},
        'source_name': None,
        'source_url': None,
        'content_hash': 'a' * 64,
        'role': 'passage',
        'sort_order': 0,
        'display_config': {},
    }
    materials = [
        {**common, 'id': 201, 'question_id': 101},
        {**common, 'id': 202, 'question_id': 102},
    ]

    catalog = PracticeService._attach_delivery_materials(items=items, materials=materials)

    assert len(catalog) == 1
    assert catalog[0]['material_revision_id'] == 10
    assert items[0]['materials'][0]['id'] == 201
    assert items[1]['materials'][0]['id'] == 202


def test_question_publish_rejects_unpublished_material(monkeypatch: MonkeyPatch) -> None:
    """题目发布前必须先发布其固定材料版本"""

    async def fake_get_reference_states(
        _db: AsyncSession | None,
        references: list[tuple[int, int]],
    ) -> dict[tuple[int, int], dict[str, Any]]:
        await asyncio.sleep(0)
        assert references == [(1, 10)]
        return {
            (1, 10): {
                'material_status': 'active',
                'revision_status': 'draft',
                'content_hash': None,
            }
        }

    monkeypatch.setattr(
        material_service_module.material_revision_dao,
        'get_reference_states',
        fake_get_reference_states,
    )

    with pytest.raises(errors.ConflictError, match='材料版本尚未发布'):
        run(
            material_service.ensure_references(
                db=None,
                items=[QuestionMaterialParam(material_id=1, material_revision_id=10)],
                publishable=True,
            )
        )


def test_question_publish_accepts_retired_material_revision(monkeypatch: MonkeyPatch) -> None:
    """历史已发布材料版本退役后仍可被固定引用"""

    async def fake_get_reference_states(
        _db: AsyncSession | None,
        references: list[tuple[int, int]],
    ) -> dict[tuple[int, int], dict[str, Any]]:
        await asyncio.sleep(0)
        assert references == [(1, 10)]
        return {
            (1, 10): {
                'material_status': 'active',
                'revision_status': 'retired',
                'content_hash': 'a' * 64,
            }
        }

    monkeypatch.setattr(
        material_service_module.material_revision_dao,
        'get_reference_states',
        fake_get_reference_states,
    )

    run(
        material_service.ensure_references(
            db=None,
            items=[QuestionMaterialParam(material_id=1, material_revision_id=10)],
            publishable=True,
        )
    )
