import asyncio
import json

from collections.abc import Iterator
from typing import Any

import pytest

from sqlalchemy import create_engine

from backend.app.question_bank_v2.crud.crud_practice import practice_session_dao, practice_session_item_dao


class MemorySession:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    async def execute(self, statement: Any) -> Any:
        return self.connection.execute(statement)


@pytest.fixture
def db() -> Iterator[MemorySession]:
    """执行真实投递与报告 SQL，覆盖无题库关联的历史导入会话"""
    engine = create_engine('sqlite://')
    with engine.connect() as connection:
        tables = {
            'practice_session': 'id INTEGER, user_id INTEGER',
            'practice_session_item': (
                'id INTEGER, session_id INTEGER, position INTEGER, question_id INTEGER, bank_item_id INTEGER, '
                'max_score NUMERIC, display_config JSON, deleted INTEGER'
            ),
            'practice_session_response': (
                'session_item_id INTEGER, response_data JSON, status TEXT, is_correct BOOLEAN, score NUMERIC, '
                'is_flagged BOOLEAN, duration_ms INTEGER, save_version INTEGER, grading_status TEXT, deleted INTEGER'
            ),
            'question': (
                'id INTEGER, question_type TEXT, stem TEXT, content_format TEXT, option_data JSON, '
                'difficulty NUMERIC, deleted INTEGER'
            ),
            'bank_item': 'id INTEGER, section_id INTEGER, exam_year INTEGER, deleted INTEGER',
            'bank_section': 'id INTEGER, name TEXT, deleted INTEGER',
            'wrong_question_state': (
                'user_id INTEGER, question_id INTEGER, entry_metadata JSON, status TEXT, deleted INTEGER'
            ),
        }
        for name, columns in tables.items():
            connection.exec_driver_sql(f'CREATE TABLE qbank_v2_{name} ({columns})')
        connection.exec_driver_sql('INSERT INTO qbank_v2_practice_session VALUES (10,7),(20,8)')
        connection.exec_driver_sql("INSERT INTO qbank_v2_bank_section VALUES (11,'正式题库章节',0)")
        connection.exec_driver_sql('INSERT INTO qbank_v2_bank_item VALUES (101,11,2026,0)')
        for question_id in range(1, 7):
            connection.exec_driver_sql(
                "INSERT INTO qbank_v2_question VALUES (?, 'single_choice', '题干', 'html', '[]', NULL, 0)",
                (question_id,),
            )
            connection.exec_driver_sql(
                "INSERT INTO qbank_v2_practice_session_item VALUES (?,10,?,?,?,2,'{}',0)",
                (question_id, question_id - 1, question_id, 101 if question_id == 3 else None),
            )
        connection.exec_driver_sql("INSERT INTO qbank_v2_practice_session_item VALUES (20,20,0,1,NULL,2,'{}',0)")
        # 同一题允许不同用户有不同来源章节；旧的软删除记录不得导致重复投递。
        for user_id, question_id, metadata, status, deleted in (
            (7, 1, {'section_name': '  资料分析  '}, 'active', 0),
            (7, 2, {'section_name': '判断推理'}, 'resolved', 0),
            (7, 3, {'section_name': '不应覆盖正式章节'}, 'active', 0),
            (7, 4, {'section_name': '  '}, 'active', 0),
            (7, 5, {}, 'active', 0),
            (8, 1, {'section_name': '另一用户的章节'}, 'active', 0),
            (8, 6, {'section_name': '仅另一用户拥有'}, 'active', 0),
            (7, 1, {'section_name': '旧章节'}, 'active', 99),
        ):
            connection.exec_driver_sql(
                'INSERT INTO qbank_v2_wrong_question_state VALUES (?,?,?,?,?)',
                (user_id, question_id, json.dumps(metadata), status, deleted),
            )
        yield MemorySession(connection)
    engine.dispose()


@pytest.mark.parametrize('report', [False, True])
def test_imported_sections_are_available_in_existing_delivery_and_report(db: MemorySession, *, report: bool) -> None:
    read = practice_session_dao.get_report_items if report else practice_session_item_dao.get_all
    rows = asyncio.run(read(db, 10))
    assert [row['question_id'] for row in rows] == [1, 2, 3, 4, 5, 6]
    assert [row['section_name'] for row in rows] == ['资料分析', '判断推理', '正式题库章节', None, None, None]
    assert [row['section_id'] for row in rows] == [None, None, 11, None, None, None]
    assert [row['position'] for row in rows] == list(range(6))


@pytest.mark.parametrize('report', [False, True])
def test_section_fallback_is_scoped_to_the_session_owner(db: MemorySession, *, report: bool) -> None:
    read = practice_session_dao.get_report_items if report else practice_session_item_dao.get_all
    rows = asyncio.run(read(db, 20))
    assert len(rows) == 1
    assert rows[0]['section_name'] == '另一用户的章节'
