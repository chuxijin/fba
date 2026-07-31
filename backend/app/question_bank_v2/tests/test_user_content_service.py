import asyncio

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.app.question_bank_v2.schema.user_content import CreateQuestionFavoriteParam
from backend.app.question_bank_v2.service.user_content_service import UserContentService


def test_favorite_tags_are_trimmed_and_deduplicated() -> None:
    """收藏标签应清理空白并按输入顺序去重"""
    obj = CreateQuestionFavoriteParam(
        question_id=1,
        tags=[' 易错 ', '', '重点', '易错'],
    )

    assert obj.tags == ['易错', '重点']


def test_knowledge_groups_build_flat_nodes() -> None:
    groups = UserContentService._build_groups(
        group_by='knowledge_point',
        rows=[{'id': 101, 'name': '阅读理解', 'count': 3}],
    )

    assert groups[0].id == 101
    assert groups[0].count == 3


def test_existing_favorite_backfills_bank_item_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """重复收藏应为缺少题库上下文的旧记录补齐编排项"""
    now = datetime.now(UTC)
    existing = SimpleNamespace(id=3, bank_item_id=None)
    detail = {
        'id': 3,
        'question_id': 11,
        'folder_id': None,
        'folder_name': None,
        'bank_item_id': 21,
        'tags': [],
        'remark': None,
        'is_pinned': False,
        'pinned_time': None,
        'stem': '题干',
        'question_type': 'single_choice',
        'difficulty': Decimal('2.0'),
        'created_time': now,
        'updated_time': now,
    }
    get_by_question = AsyncMock(return_value=existing)
    update = AsyncMock()
    get_detail = AsyncMock(return_value=detail)
    resolve_context = AsyncMock()
    dao_path = 'backend.app.question_bank_v2.service.user_content_service.question_favorite_dao'
    monkeypatch.setattr(f'{dao_path}.get_by_question', get_by_question)
    monkeypatch.setattr(f'{dao_path}.update', update)
    monkeypatch.setattr(f'{dao_path}.get_detail', get_detail)
    monkeypatch.setattr(UserContentService, '_resolve_question_context', resolve_context)

    db = AsyncMock()
    result = asyncio.run(
        UserContentService.create_favorite(
            db=db,
            user_id=7,
            obj=CreateQuestionFavoriteParam(question_id=11, bank_item_id=21),
        )
    )

    resolve_context.assert_awaited_once()
    update.assert_awaited_once_with(
        db,
        3,
        user_id=7,
        data={'bank_item_id': 21, 'updated_by': 7},
    )
    assert result.bank_item_id == 21


def test_note_detail_exposes_client_public_flag() -> None:
    """规范化可见性同时提供小程序可直接使用的公开布尔值"""
    now = datetime.now(UTC)
    detail = UserContentService._note_detail({
        'id': 1,
        'user_id': 7,
        'user_nickname': '用户',
        'question_id': 11,
        'bank_item_id': None,
        'content': '笔记',
        'content_format': 'markdown',
        'visibility': 'public',
        'status': 'published',
        'like_count': 2,
        'dislike_count': 0,
        'view_count': 5,
        'is_featured': False,
        'my_vote': None,
        'stem': '题干',
        'question_type': 'single_choice',
        'difficulty': Decimal('2.0'),
        'created_time': now,
        'updated_time': None,
    })

    assert detail.visibility == 'public'
    assert detail.is_public is True
