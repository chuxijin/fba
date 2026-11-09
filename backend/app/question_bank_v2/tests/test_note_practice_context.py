"""笔记缺少保存的编排上下文时，列表分组与笔记练习必须仍能命中同一题。"""

import asyncio

from collections.abc import Iterator
from typing import Any

import pytest

from sqlalchemy import create_engine

from backend.app.question_bank_v2.crud.crud_practice import PracticeCandidate, practice_session_item_dao
from backend.app.question_bank_v2.crud.crud_user_content import question_note_dao


class MemorySession:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    async def execute(self, statement: Any) -> Any:
        return self.connection.execute(statement)


@pytest.fixture
def db() -> Iterator[MemorySession]:
    engine = create_engine('sqlite://')
    with engine.connect() as connection:
        tables = {
            'bank': 'id INTEGER, current_revision_id INTEGER, deleted INTEGER',
            'bank_revision': 'id INTEGER, bank_id INTEGER, revision_no INTEGER, name TEXT, deleted INTEGER',
            'bank_item': (
                'id INTEGER, question_id INTEGER, bank_revision_id INTEGER, section_id INTEGER, '
                'score NUMERIC, settings JSON, exam_year INTEGER, deleted INTEGER'
            ),
            'bank_section': 'id INTEGER, name TEXT',
            'question': 'id INTEGER, default_score NUMERIC, deleted INTEGER, question_type TEXT',
            'question_note': 'id INTEGER, user_id INTEGER, question_id INTEGER, bank_item_id INTEGER, deleted INTEGER',
        }
        for name, columns in tables.items():
            connection.exec_driver_sql(f'CREATE TABLE qbank_v2_{name} ({columns})')
        connection.exec_driver_sql('INSERT INTO qbank_v2_bank VALUES (1,12,0),(2,21,0)')
        connection.exec_driver_sql(
            "INSERT INTO qbank_v2_bank_revision VALUES (11,1,1,'旧卷',0),(12,1,2,'新卷',0),(21,2,1,'另一卷',0)"
        )
        connection.exec_driver_sql("INSERT INTO qbank_v2_bank_section VALUES (100,'旧章'),(110,'章一'),(111,'章二')")
        for qid in range(101, 111):
            connection.exec_driver_sql(
                "INSERT INTO qbank_v2_question VALUES (?,1,?,'single_choice')", (qid, int(qid == 106))
            )
        for item_id, question_id, revision_id, section_id, deleted in [
            (1, 101, 11, 100, 0),
            (2, 101, 12, 110, 0),
            (3, 101, 12, 111, 0),
            (4, 102, 11, 100, 0),
            (5, 103, 12, 110, 0),
            (6, 104, 12, 110, 0),
            (7, 105, 12, 110, 0),
            (8, 108, 12, 110, 1),
            (9, 109, 21, None, 0),
            (10, 109, 12, 110, 0),
            (11, 110, 21, None, 0),
            (12, 106, 12, 110, 0),
            (20, 101, 21, None, 0),
        ]:
            connection.exec_driver_sql(
                'INSERT INTO qbank_v2_bank_item VALUES (?,?,?,?,2,?,2026,?)',
                (item_id, question_id, revision_id, section_id, '{"saved_layout":true}', deleted),
            )
        connection.exec_driver_sql(
            'INSERT INTO qbank_v2_question_note VALUES '
            '(1,7,101,NULL,0),(2,7,102,4,0),(3,7,103,999,0),(4,8,104,NULL,0),'
            '(5,7,105,NULL,1),(6,7,106,NULL,0),(7,7,107,NULL,0),(8,7,108,NULL,0),'
            '(9,7,109,9,0),(10,7,110,NULL,0)'
        )
        yield MemorySession(connection)
    engine.dispose()


def candidates(db: MemorySession, **overrides: Any) -> list[PracticeCandidate]:
    options = {
        'user_id': 7,
        'source_type': 'note',
        'bank_id': 1,
        'section_ids': [],
        'favorite_folder_id': None,
        'question_ids': [],
        'knowledge_point_ids': [],
        'question_types': [],
        'year_start': None,
        'year_end': None,
        'shuffle': False,
        'limit': 500,
        **overrides,
    }
    return asyncio.run(practice_session_item_dao.get_user_candidates(db, **options))


def test_note_without_saved_placement_is_delivered_in_its_listed_bank(db: MemorySession) -> None:
    rows = candidates(db)
    assert [(item.question_id, item.bank_item_id) for item in rows] == [(103, 5), (102, 4), (101, 3)]
    assert rows[-1].max_score == 2
    assert rows[-1].display_config == {'saved_layout': True}


def test_list_and_delivery_use_the_same_current_revision_and_duplicate_tiebreak(db: MemorySession) -> None:
    db.connection.exec_driver_sql('DELETE FROM qbank_v2_question_note WHERE id <> 1')
    groups = asyncio.run(question_note_dao.get_group_counts(db, user_id=7, group_by='bank', knowledge_system_ids=[]))
    assert {(item['bank_id'], item['bank_revision_id'], item['section_id']) for item in groups} == {
        (1, 12, 111),
        (2, 21, None),
    }
    for group in groups:
        rows = candidates(db, bank_id=group['bank_id'])
        assert len(rows) == group['count'] == 1
        assert rows[0].question_id == 101


def test_explicit_saved_context_is_not_reassigned_to_a_different_bank(db: MemorySession) -> None:
    rows = candidates(db, bank_id=2)
    assert [(item.question_id, item.bank_item_id) for item in rows] == [(110, 11), (109, 9), (101, 20)]
    assert 109 not in {item.question_id for item in candidates(db, bank_id=1)}


def test_section_filter_uses_resolved_context_instead_of_null_saved_id(db: MemorySession) -> None:
    assert [item.question_id for item in candidates(db, section_ids=[110])] == [103]
    assert [item.question_id for item in candidates(db, section_ids=[111])] == [101]
    assert [item.question_id for item in candidates(db, section_ids=[100])] == [102]


@pytest.mark.parametrize('shuffle', [False, True])
def test_unscoped_notes_do_not_duplicate_shared_questions(db: MemorySession, *, shuffle: bool) -> None:
    rows = candidates(db, bank_id=None, shuffle=shuffle)
    ids = [item.question_id for item in rows]
    assert len(ids) == len(set(ids))
    assert ids.count(101) == 1
    assert {104, 105, 106}.isdisjoint(ids)  # 其他用户、已删除笔记、已删除题目不投递。
    orphan = next(item for item in rows if item.question_id == 107)
    assert orphan.bank_item_id is None
    assert orphan.max_score == 1


def test_missing_bank_does_not_fall_back_to_unrelated_notes(db: MemorySession) -> None:
    assert candidates(db, bank_id=999) == []
    assert [item.question_id for item in candidates(db, user_id=8)] == [104]
    assert [item.question_id for item in candidates(db, limit=1)] == [103]
