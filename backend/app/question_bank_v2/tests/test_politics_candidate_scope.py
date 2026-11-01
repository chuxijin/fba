"""政治卷主标注过滤使用真实内存SQL，通用知识点抽题不改变口径。"""

from collections.abc import Iterator

import pytest

from backend.app.question_bank_v2.tests.test_knowledge_practice import (
    MemorySession,
    candidates,
)
from backend.app.question_bank_v2.tests.test_knowledge_practice import (
    db as knowledge_db,
)


@pytest.fixture
def db() -> Iterator[MemorySession]:
    yield from knowledge_db.__wrapped__()


def test_politics_primary_scope_excludes_secondary_labels(db: MemorySession) -> None:
    db.connection.exec_driver_sql(
        "ALTER TABLE qbank_v2_question_knowledge_point ADD COLUMN role TEXT DEFAULT 'primary'"
    )
    db.connection.exec_driver_sql(
        "UPDATE qbank_v2_question_knowledge_point SET role='secondary' WHERE question_id=1 AND knowledge_point_id=301"
    )

    assert candidates(db, knowledge_point_ids=[301]) == [1, 2]
    assert candidates(db, knowledge_point_ids=[301], knowledge_point_role='primary') == [2]
    assert candidates(db, knowledge_point_ids=[201, 301], knowledge_point_role='primary') == [1, 2]
    assert candidates(db, knowledge_point_ids=[], knowledge_point_role='primary') == []


def test_politics_primary_scope_preserves_visibility_and_deleted_filters(db: MemorySession) -> None:
    db.connection.exec_driver_sql(
        "ALTER TABLE qbank_v2_question_knowledge_point ADD COLUMN role TEXT DEFAULT 'primary'"
    )

    assert candidates(db, knowledge_point_ids=[201, 301, 401], knowledge_point_role='primary') == [1, 2, 4]
    assert candidates(db, knowledge_point_ids=[999], knowledge_point_role='primary') == [8]
