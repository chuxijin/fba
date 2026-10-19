"""用内存数据库验证收藏/笔记跨领域、共享题目及历史上下文的实际筛选结果。"""

import asyncio

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from sqlalchemy import create_engine

from backend.app.question_bank_v2.crud.crud_review import wrong_question_state_dao
from backend.app.question_bank_v2.crud.crud_user_content import question_favorite_dao, question_note_dao
from backend.app.question_bank_v2.model.bank import QbBank
from backend.app.question_bank_v2.model.review import QbWrongQuestionState
from backend.app.question_bank_v2.model.user_content import QbQuestionFavorite, QbQuestionNote
from backend.app.question_bank_v2.service.user_content_service import UserContentService


class MemorySession:
    def __init__(self, connection: Any) -> None:
        self.connection = connection
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> Any:
        self.statements.append(statement)
        return self.connection.execute(statement)


@pytest.fixture
def db() -> Iterator[MemorySession]:
    engine = create_engine('sqlite://')
    with engine.connect() as connection:
        # 仅创建查询需要的列，避免引入生产数据库、完整应用启动和其他模型的外键依赖。
        tables = {
            'bank': 'id INTEGER, current_revision_id INTEGER, deleted INTEGER',
            'bank_revision': 'id INTEGER, bank_id INTEGER, revision_no INTEGER, name TEXT',
            'bank_category': 'id INTEGER, bank_id INTEGER, category_id INTEGER, deleted INTEGER',
            'bank_item': 'id INTEGER, question_id INTEGER, bank_revision_id INTEGER, section_id INTEGER',
            'bank_section': 'id INTEGER, name TEXT',
            'favorite_folder': 'id INTEGER, user_id INTEGER, deleted INTEGER, status TEXT',
            'question_favorite': (
                'id INTEGER, user_id INTEGER, question_id INTEGER, bank_item_id INTEGER, '
                'folder_id INTEGER, deleted INTEGER'
            ),
            'question_note': (
                'id INTEGER, user_id INTEGER, question_id INTEGER, bank_item_id INTEGER, deleted INTEGER, '
                'visibility TEXT, is_featured BOOLEAN'
            ),
            'knowledge_point': 'id INTEGER, name TEXT, system_id INTEGER, sort_order INTEGER, deleted INTEGER',
            'question_knowledge_point': 'question_id INTEGER, knowledge_point_id INTEGER, deleted INTEGER',
        }
        for name, columns in tables.items():
            connection.exec_driver_sql(f'CREATE TABLE qbank_v2_{name} ({columns})')
        for statement in (
            'INSERT INTO qbank_v2_bank VALUES (10, 102, 0), (20, 201, 0), (30, 301, 1), (40, 401, 0)',
            "INSERT INTO qbank_v2_bank_revision VALUES (101,10,1,'公旧版'), (102,10,2,'公'),"
            "(201,20,1,'研'), (301,30,1,'删除库'), (401,40,1,'删除分类')",
            'INSERT INTO qbank_v2_bank_category VALUES (1,10,1,0), (2,20,2,0), (3,20,22,0), (4,30,2,0), (5,40,2,1)',
            'INSERT INTO qbank_v2_bank_item VALUES (111,11,101,NULL), (112,11,102,NULL), (212,12,201,NULL),'
            '(113,13,102,NULL), (213,13,201,NULL), (114,14,102,NULL), (214,14,201,NULL),'
            '(215,15,201,NULL), (316,16,301,NULL), (417,17,401,NULL)',
            "INSERT INTO qbank_v2_favorite_folder VALUES (1,7,0,'active'), (2,7,0,'active'),"
            "(3,7,0,'active'), (4,7,0,'active')",
            'INSERT INTO qbank_v2_question_favorite VALUES (1,7,11,111,1,0), (2,7,12,212,2,0),'
            '(3,7,13,113,1,0), (4,7,14,NULL,NULL,0), (5,7,15,999,NULL,0), (6,7,16,316,3,0),'
            '(7,7,17,417,3,0), (8,7,12,212,2,1), (9,8,12,212,2,0)',
            'INSERT INTO qbank_v2_question_note '
            "SELECT id,user_id,question_id,bank_item_id,deleted,CASE WHEN question_id IN (12,13) THEN 'public' "
            "ELSE 'private' END, question_id=14 FROM qbank_v2_question_favorite",
            "INSERT INTO qbank_v2_knowledge_point VALUES (50,'共享知识点',5,0,0)",
            'INSERT INTO qbank_v2_question_knowledge_point '
            'SELECT DISTINCT question_id,50,0 FROM qbank_v2_question_favorite',
        ):
            connection.exec_driver_sql(statement)
        yield MemorySession(connection)
    engine.dispose()


@pytest.mark.parametrize('dao', [question_favorite_dao, question_note_dao])
@pytest.mark.parametrize('categories,expected', [([1], 3), ([2, 22], 3), ([], 0), (None, 7)])
def test_statistics_and_bank_groups_share_scope(db: MemorySession, dao: Any, categories: Any, expected: int) -> None:
    stats = asyncio.run(dao.get_statistics(db, user_id=7, domain_category_ids=categories))
    assert stats['total_count'] == expected
    if categories is None:
        assert stats.get('folder_count', 4) == 4
        return
    groups = asyncio.run(
        dao.get_group_counts(
            db,
            user_id=7,
            group_by='bank',
            knowledge_system_ids=[],
            domain_category_ids=categories,
        )
    )
    assert sum(row['count'] for row in groups) == expected
    assert {row['bank_id'] for row in groups} == ({10} if categories == [1] else {20} if categories else set())
    assert stats.get('folder_count', int(bool(categories))) == int(bool(categories))
    if dao is question_note_dao:
        assert stats['public_count'] == int(bool(categories))
        assert stats['featured_count'] == int(bool(categories))
    if categories == [1]:
        assert any(row['bank_revision_id'] == 101 for row in groups), '保存的旧版本上下文必须保留'


@pytest.mark.parametrize(
    'dao,model', [(question_favorite_dao, QbQuestionFavorite), (question_note_dao, QbQuestionNote)]
)
@pytest.mark.parametrize('categories,expected', [([1], {11, 13, 14}), ([2, 22], {12, 14, 15}), ([], set())])
def test_knowledge_groups_keep_record_domain(
    db: MemorySession, dao: Any, model: Any, categories: Any, expected: set
) -> None:
    # SQLite 不支持生产库的 DISTINCT 带分隔符字符串聚合；保留原查询的 FROM/WHERE 验证实际命中题目。
    capture = AsyncMock()
    capture.execute.return_value.mappings = lambda: SimpleNamespace(all=list)
    asyncio.run(
        dao.get_group_counts(
            capture,
            user_id=7,
            group_by='knowledge_point',
            knowledge_system_ids=[5],
            domain_category_ids=categories,
        )
    )
    statement = capture.execute.call_args.args[0]
    ids = (
        db.connection
        .execute(statement.with_only_columns(model.question_id).group_by(None).order_by(None).distinct())
        .scalars()
        .all()
    )
    assert set(ids) == expected


@pytest.mark.parametrize('category,expected', [(1, {(10, 11), (10, 13)}), (2, {(20, 12), (20, 13)})])
def test_shared_wrong_question_does_not_add_other_domain_bank(
    db: MemorySession,
    category: int,
    expected: set[tuple[int, int]],
) -> None:
    db.connection.exec_driver_sql('ALTER TABLE qbank_v2_bank_item ADD COLUMN deleted INTEGER DEFAULT 0')
    db.connection.exec_driver_sql(
        'CREATE TABLE qbank_v2_wrong_question_state '
        '(question_id INTEGER, source_bank_item_id INTEGER, user_id INTEGER, '
        'status TEXT, deleted INTEGER, entry_source TEXT, entry_metadata JSON)'
    )
    db.connection.exec_driver_sql(
        'INSERT INTO qbank_v2_wrong_question_state VALUES '
        "(11,111,7,'active',0,'attempt','{}'), (12,212,7,'active',0,'attempt','{}'), "
        "(13,NULL,7,'active',0,'attempt','{}')"
    )
    capture = AsyncMock()
    capture.execute.return_value.mappings = lambda: SimpleNamespace(all=list)
    asyncio.run(
        wrong_question_state_dao.get_group_counts(
            capture,
            user_id=7,
            group_by='bank',
            knowledge_system_ids=[],
            domain_category_ids=[category],
        )
    )
    bank_statement = capture.execute.call_args_list[0].args[0]
    rows = db.connection.execute(
        bank_statement
        .with_only_columns(
            QbBank.id,
            QbWrongQuestionState.question_id,
        )
        .group_by(None)
        .order_by(None)
        .distinct()
    ).all()
    assert set(rows) == expected


@pytest.mark.parametrize('kind', ['favorite', 'note'])
@pytest.mark.parametrize('domain,category_ids', [(2, [2, 22]), (999, []), (None, None)])
def test_service_passes_resolved_scope_to_counts_and_groups(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    domain: int | None,
    category_ids: list[int] | None,
) -> None:
    path = 'backend.app.question_bank_v2.service.user_content_service'
    resolve = AsyncMock(return_value=domain)
    subtree = AsyncMock(return_value=category_ids)
    stats = AsyncMock(
        return_value={'total_count': 0, 'folder_count': 0}
        if kind == 'favorite'
        else {
            'total_count': 0,
            'public_count': 0,
            'featured_count': 0,
        }
    )
    groups = AsyncMock(return_value=[])
    monkeypatch.setattr(f'{path}.knowledge_service.resolve_optional_domain_category_id', resolve)
    monkeypatch.setattr(f'{path}.category_dao.get_subtree_ids_by_path', subtree)
    monkeypatch.setattr(f'{path}.question_{kind}_dao.get_statistics', stats)
    monkeypatch.setattr(f'{path}.question_{kind}_dao.get_group_counts', groups)
    monkeypatch.setattr(f'{path}.content_group_service.build_bank_tree', AsyncMock(return_value=[]))
    session = object()
    asyncio.run(
        getattr(UserContentService, f'get_{kind}_statistics')(
            db=session,
            user_id=7,
            group_by='bank',
            domain_category_id=domain,
        )
    )
    resolve.assert_awaited_once_with(db=session, user_id=7, domain_category_id=domain)
    assert stats.call_args.kwargs['domain_category_ids'] == category_ids
    assert groups.call_args.kwargs['domain_category_ids'] == category_ids
    if domain is None:
        subtree.assert_not_awaited()
