"""以真实 SQL 验证批量合集作用域、版本优先级和固定查询次数。"""

import asyncio

from collections.abc import Iterator
from typing import Any

import pytest

from pydantic import ValidationError
from sqlalchemy import create_engine

from backend.app.question_bank_v2.schema.analytics import GetCollectionProgressBatchParam
from backend.app.question_bank_v2.service.analytics_service import AnalyticsService
from backend.common.exception import errors


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
        tables = {
            'collection': 'id INTEGER, parent_id INTEGER, status TEXT, visibility TEXT, deleted INTEGER',
            'collection_bank': (
                'id INTEGER, collection_id INTEGER, bank_id INTEGER, bank_revision_id INTEGER, '
                'follow_latest BOOLEAN, deleted INTEGER, is_active BOOLEAN'
            ),
            'bank': 'id INTEGER, current_revision_id INTEGER, visibility TEXT, status TEXT, deleted INTEGER',
            'bank_revision': 'id INTEGER, bank_id INTEGER, revision_no INTEGER, status TEXT, deleted INTEGER',
            'bank_item': 'id INTEGER, bank_revision_id INTEGER, is_active BOOLEAN, deleted INTEGER',
            'user_bank_item_progress': (
                'id INTEGER, user_id INTEGER, bank_item_id INTEGER, last_is_correct BOOLEAN, deleted INTEGER'
            ),
        }
        for name, columns in tables.items():
            connection.exec_driver_sql(f'CREATE TABLE qbank_v2_{name} ({columns})')
        for sql in (
            "INSERT INTO qbank_v2_collection VALUES (1,NULL,'active','public',0),(2,1,'active','public',0),"
            "(3,NULL,'active','public',0),(4,1,'active','private',0),(5,4,'active','public',0),"
            "(6,1,'inactive','public',0),(7,NULL,'active','public',1),(8,NULL,'active','public',0)",
            "INSERT INTO qbank_v2_bank VALUES (10,102,'public','active',0),(20,201,'public','active',0),"
            "(30,301,'private','active',0),(40,401,'public','inactive',0),(50,501,'public','active',1)",
            "INSERT INTO qbank_v2_bank_revision VALUES (101,10,1,'retired',0),(102,10,2,'published',0),"
            "(201,20,1,'published',0),(301,30,1,'published',0),(401,40,1,'published',0),(501,50,1,'published',0)",
            'INSERT INTO qbank_v2_collection_bank VALUES (1,1,10,101,0,0,1),(2,2,10,NULL,1,0,1),'
            '(3,3,10,101,0,0,1),(4,1,20,NULL,1,0,1),(5,3,20,NULL,1,0,1),'
            '(6,4,10,101,0,0,1),(7,5,20,NULL,1,0,1),(8,6,20,NULL,1,0,1),'
            '(9,1,30,NULL,1,0,1),(10,1,40,NULL,1,0,1),(11,1,50,NULL,1,0,1),'
            '(12,1,10,102,0,1,1),(13,1,10,102,0,0,0)',
            'INSERT INTO qbank_v2_bank_item VALUES (1,101,1,0),(2,101,1,0),'
            '(3,102,1,0),(4,102,1,0),(5,102,1,0),(6,102,0,0),(7,102,1,1),'
            '(8,201,1,0),(9,201,1,0)',
            'INSERT INTO qbank_v2_user_bank_item_progress VALUES (1,7,1,1,0),'
            '(2,7,3,1,0),(3,7,4,0,0),(4,7,5,NULL,0),(5,8,2,1,0),(6,7,8,1,1)',
        ):
            connection.exec_driver_sql(sql)
        yield MemorySession(connection)
    engine.dispose()


def summaries(db: MemorySession, ids: list[int], **kwargs: Any) -> Any:
    return asyncio.run(AnalyticsService.get_collection_progress_summaries(
        db=db, user_id=7, collection_ids=ids, **kwargs
    ))


def test_batch_deduplicates_roots_and_queries_all_progress_once(db: MemorySession) -> None:
    result = summaries(db, [1, 3, 2, 1, 8])
    assert [item.collection_id for item in result.items] == [1, 3, 2, 8]
    assert len(db.statements) == 3
    first, third, child, empty = result.items
    assert [(bank.bank_id, bank.bank_revision_id) for bank in first.banks] == [(10, 102), (20, 201)]
    assert first.total_count == 5
    assert first.answered_count == 3
    assert first.correct_count == 1
    assert first.wrong_count == 1
    assert first.accuracy_rate == AnalyticsService._rate(1, 2)
    assert [(bank.bank_id, bank.bank_revision_id) for bank in third.banks] == [(10, 101), (20, 201)]
    assert third.answered_count == 1  # 其他用户及已删除进度不计入。
    assert child.total_count == 3
    assert empty.total_count == 0
    assert empty.banks == []


def test_without_descendants_preserves_fixed_revision(db: MemorySession) -> None:
    result = summaries(db, [1], include_descendants=False).items[0]
    assert result.banks[0].bank_revision_id == 101
    assert result.total_count == 4
    assert result.answered_count == 1
    assert len(db.statements) == 3


def test_single_endpoint_uses_identical_batch_semantics(db: MemorySession) -> None:
    batch = summaries(db, [1, 3])
    for item in batch.items:
        single = asyncio.run(AnalyticsService.get_collection_progress_summary(
            db=db, user_id=7, collection_id=item.collection_id
        ))
        assert single == item


@pytest.mark.parametrize('root_id', [6, 7, 999])
def test_invalid_roots_reject_before_mount_or_progress_queries(db: MemorySession, root_id: int) -> None:
    with pytest.raises(errors.NotFoundError):
        summaries(db, [1, root_id])
    assert len(db.statements) == 1


@pytest.mark.parametrize('ids', [[], [0], [-1], list(range(1, 102))])
def test_batch_parameter_rejects_invalid_or_unbounded_ids(ids: list[int]) -> None:
    with pytest.raises(ValidationError):
        GetCollectionProgressBatchParam(collection_ids=ids)
