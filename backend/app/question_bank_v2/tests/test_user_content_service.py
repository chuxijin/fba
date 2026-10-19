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


class MappingResult:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def mappings(self) -> 'MappingResult':
        return self

    def all(self) -> list[dict]:
        return self.rows


def test_favorite_statistics_builds_knowledge_point_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    """按知识点统计要补出知识体系父链，不能把命中点平铺返回"""
    dao_path = 'backend.app.question_bank_v2.service.user_content_service.question_favorite_dao'

    async def fake_domain_scope(**_: object) -> tuple[int, list[int]]:
        await asyncio.sleep(0)
        return 1400, [1400]

    async def fake_system_ids(**_: object) -> list[int]:
        await asyncio.sleep(0)
        return [2]

    monkeypatch.setattr(UserContentService, '_resolve_domain_scope', fake_domain_scope)
    monkeypatch.setattr(UserContentService, '_resolve_knowledge_system_ids', fake_system_ids)
    monkeypatch.setattr(
        f'{dao_path}.get_statistics',
        AsyncMock(return_value={'total_count': 1, 'folder_count': 0}),
    )
    monkeypatch.setattr(
        f'{dao_path}.get_group_counts',
        AsyncMock(return_value=[{'id': 3, 'name': '唯物论', 'count': 1, 'question_ids': [101]}]),
    )

    db = AsyncMock()
    db.execute.side_effect = [
        MappingResult([{'id': 3, 'name': '唯物论', 'parent_id': 2, 'path': '/1/2/3/', 'sort_order': 0}]),
        MappingResult([
            {'id': 1, 'name': '政治', 'parent_id': None, 'path': '/1/', 'sort_order': 0},
            {'id': 2, 'name': '马原', 'parent_id': 1, 'path': '/1/2/', 'sort_order': 0},
        ]),
    ]

    stats = asyncio.run(
        UserContentService.get_favorite_statistics(
            db=db,
            user_id=7,
            group_by='knowledge_point',
        )
    )

    # 单一根「政治」下钻一层后，首屏直接是科目「马原」→「唯物论」
    assert [group.name for group in stats.groups] == ['马原']
    assert stats.groups[0].count == 1
    assert stats.groups[0].children[0].name == '唯物论'
    assert stats.groups[0].children[0].question_ids == [101]


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
