import asyncio
import importlib

from collections.abc import Coroutine
from decimal import Decimal
from typing import Any, TypeVar

import pytest

from fastapi import FastAPI
from pydantic import ValidationError
from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.api.router import v1 as question_bank_v2_router
from backend.app.question_bank_v2.schema.bank import CreateBankParam
from backend.app.question_bank_v2.service.catalog_service import catalog_service
from backend.app.question_bank_v2.service.preference_service import preference_service
from backend.app.question_bank_v2.service.question_service import question_service
from backend.common.exception import errors

catalog_service_module = importlib.import_module('backend.app.question_bank_v2.service.catalog_service')
preference_service_module = importlib.import_module('backend.app.question_bank_v2.service.preference_service')
T = TypeVar('T')


def run(coro: Coroutine[Any, Any, T]) -> T:
    """同步执行协程"""
    return asyncio.new_event_loop().run_until_complete(coro)


def test_create_bank_requires_primary_category_in_memberships() -> None:
    """主分类必须同时出现在题库分类关联中"""
    with pytest.raises(ValidationError, match='主分类必须包含在分类列表中'):
        CreateBankParam(
            code='cet-4',
            revision={'name': '大学英语四级'},
            category_ids=[1],
            primary_category_id=2,
        )


def test_public_catalog_builds_tree_and_applies_mount_alias(monkeypatch: MonkeyPatch) -> None:
    """公开目录应构建合集树并应用挂载展示别名"""

    async def fake_get_public_catalog(
        _db: AsyncSession | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        await asyncio.sleep(0)
        return (
            [
                {
                    'id': 1,
                    'code': 'cet',
                    'name': '四六级考试',
                    'parent_id': None,
                    'description': None,
                    'sort_order': 0,
                },
                {
                    'id': 2,
                    'code': 'cet-4',
                    'name': '四级',
                    'parent_id': 1,
                    'description': None,
                    'sort_order': 0,
                },
            ],
            [
                {
                    'collection_id': 2,
                    'mount_sort_order': 0,
                    'display_name': '历年四级真题',
                    'id': 10,
                    'code': 'cet-4-paper',
                    'visibility': 'public',
                    'status': 'active',
                    'revision_id': 100,
                    'revision_no': 1,
                    'name': '大学英语四级历年真题',
                    'bank_kind': 'paper',
                    'description': None,
                    'cover_url': None,
                    'duration_minutes': 125,
                    'pass_score': Decimal('425.00'),
                    'question_count': 57,
                    'total_score': Decimal('710.00'),
                    'primary_category_id': 2,
                    'primary_category_name': '四级',
                }
            ],
        )

    monkeypatch.setattr(catalog_service_module.collection_dao, 'get_public_catalog', fake_get_public_catalog)

    result = run(catalog_service.get_public_catalog(db=None))

    assert len(result) == 1
    assert result[0].name == '四六级考试'
    assert result[0].children[0].banks[0].name == '历年四级真题'


def test_missing_preference_returns_stable_defaults(monkeypatch: MonkeyPatch) -> None:
    """用户未初始化偏好时不应产生数据库写入"""

    async def fake_get_by_user_id(_db: AsyncSession | None, _user_id: int) -> None:
        await asyncio.sleep(0)

    monkeypatch.setattr(preference_service_module.practice_preference_dao, 'get_by_user_id', fake_get_by_user_id)

    result = run(preference_service.get(db=None, user_id=1))

    assert result.practice_mode == 'practice'
    assert result.mastery_threshold == 3
    assert result.random_practice_count == 20
    assert result.review_reminder_enabled is False
    assert result.review_reminder_timezone == 'Asia/Shanghai'
    assert result.review_daily_limit == 30
    assert result.custom_tabs == {}


def test_single_choice_answer_must_reference_an_option() -> None:
    """单选题标准答案不能引用不存在的选项"""
    with pytest.raises(errors.RequestError, match='单选题答案必须是有效选项编码'):
        question_service._validate_answer(
            question_type='single_choice',
            options=[
                {'option_code': 'A', 'content': '选项 A'},
                {'option_code': 'B', 'content': '选项 B'},
            ],
            answer_data={'correct': 'C'},
        )


def test_v2_openapi_routes_and_names_are_unique() -> None:
    """V2 路由应独立注册且操作标识不重复"""
    app = FastAPI()
    app.include_router(question_bank_v2_router)
    spec = app.openapi()
    paths = {path: operations for path, operations in spec['paths'].items() if '/qbank-v2/' in path}
    operation_ids = [operation['operationId'] for operations in paths.values() for operation in operations.values()]

    assert len(paths) == 34
    assert len(operation_ids) == 47
    assert '/api/v1/qbank-v2/sessions' in paths
    assert '/api/v1/qbank-v2/sessions/{session_key}' in paths
    assert '/api/v1/qbank-v2/sessions/{session_key}/items/{session_item_id}/response' in paths
    assert '/api/v1/qbank-v2/sessions/{session_key}/items/{session_item_id}/submit' in paths
    assert '/api/v1/qbank-v2/sessions/{session_key}/items/{session_item_id}/solution' in paths
    assert '/api/v1/qbank-v2/sessions/{session_key}/submit' in paths
    assert '/api/v1/qbank-v2/wrong-questions' in paths
    assert '/api/v1/qbank-v2/wrong-questions/due' in paths
    assert '/api/v1/qbank-v2/wrong-questions/external' in paths
    assert '/api/v1/qbank-v2/wrong-questions/{wrong_state_id}/reviews' in paths
    assert len(operation_ids) == len(set(operation_ids))
