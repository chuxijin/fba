"""回归测试：做题数据重置的删除顺序必须满足外键依赖。

`qbank_v2_user_bank_item_progress.last_attempt_id` 以 RESTRICT 指向
`qbank_v2_question_attempt(user_id, question_id, id)`（约束 fk_qbv2_ubip_last_attempt），
先删作答事实会被外键挡下，导致整批重置失败。

反过来，作答事实自身以 RESTRICT 指向会话/投递题目，所以会话必须在作答事实之后删。
"""

from __future__ import annotations

from typing import Any

from backend.app.question_bank_v2.service.practice_data_reset_service import (
    PracticeDataResetService,
)

ATTEMPT_TABLE = 'qbank_v2_question_attempt'

# 以 RESTRICT / CASCADE 指向 qbank_v2_question_attempt 的表，必须在作答事实之前清空
ATTEMPT_DEPENDENT_TABLES = (
    'qbank_v2_question_review',
    'qbank_v2_wrong_question_state',
    'qbank_v2_evaluation_run',
    'qbank_v2_question_attempt_asset',
    'qbank_v2_question_attempt_knowledge_point',
    'qbank_v2_user_bank_item_progress',
)

# 作答事实指向的表，必须在作答事实之后清空
ATTEMPT_PARENT_TABLES = (
    'qbank_v2_practice_session_response',
    'qbank_v2_practice_session_item',
    'qbank_v2_practice_session',
)


class _FakeResult:
    rowcount = 0


class _RecordingSession:
    """只记录 DELETE 目标表顺序的假会话，不触碰数据库。"""

    def __init__(self) -> None:
        self.deleted_tables: list[str] = []

    async def execute(self, statement: Any) -> _FakeResult:
        self.deleted_tables.append(statement.table.name)
        return _FakeResult()

    async def flush(self) -> None:
        return None


async def _deleted_tables() -> list[str]:
    db = _RecordingSession()
    await PracticeDataResetService.reset_user_practice_data(db=db, user_id=1)  # type: ignore[arg-type]
    return db.deleted_tables


async def test_attempt_dependent_tables_are_deleted_before_attempts() -> None:
    tables = await _deleted_tables()

    assert ATTEMPT_TABLE in tables
    attempt_index = tables.index(ATTEMPT_TABLE)
    for dependent in ATTEMPT_DEPENDENT_TABLES:
        assert dependent in tables, f'{dependent} 未被重置'
        assert tables.index(dependent) < attempt_index, f'{dependent} 必须在 {ATTEMPT_TABLE} 之前删除'


async def test_attempt_parent_tables_are_deleted_after_attempts() -> None:
    tables = await _deleted_tables()

    attempt_index = tables.index(ATTEMPT_TABLE)
    for parent in ATTEMPT_PARENT_TABLES:
        assert parent in tables, f'{parent} 未被重置'
        assert tables.index(parent) > attempt_index, f'{parent} 必须在 {ATTEMPT_TABLE} 之后删除'


async def test_reset_covers_every_user_scoped_table_exactly_once() -> None:
    tables = await _deleted_tables()

    assert len(tables) == len(set(tables)), f'存在重复删除：{tables}'
