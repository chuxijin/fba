"""练习写入加锁顺序回归：用户父锁先于会话/作答读取，题目锁升序去重。

只编译 SQL 并记录 db.execute 调用顺序，不连接任何真实数据库。
"""

import re

from typing import Any

from backend.app.question_bank_v2.crud.crud_evaluation import evaluation_run_dao
from backend.app.question_bank_v2.crud.crud_practice import practice_session_dao
from backend.app.question_bank_v2.service.attempt_projection_service import AttemptProjectionService


class _EmptyResult:
    def scalars(self) -> Any:
        return self

    def first(self) -> None:
        return None


class _RecordingDB:
    """记录每条被执行语句，按记录顺序验证加锁先后。"""

    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> _EmptyResult:
        self.statements.append(statement)
        return _EmptyResult()


def _sql(statement: Any) -> str:
    return str(statement.compile(compile_kwargs={'literal_binds': True})).upper()


def _assert_user_lock_first(db: _RecordingDB) -> str:
    """用户父锁必须是第一条语句，之后的读取才允许 for_update。"""
    assert len(db.statements) >= 2
    user_sql = _sql(db.statements[0])
    assert 'SYS_USER' in user_sql
    assert 'FOR UPDATE' in user_sql
    read_sql = _sql(db.statements[1])
    assert 'SYS_USER' not in read_sql
    return read_sql


async def test_get_by_key_locks_user_before_session_read() -> None:
    """按会话标识取写锁时，用户父锁先于会话行 for_update 读取。"""
    db = _RecordingDB()

    session = await practice_session_dao.get_by_key(db, 'session-123', user_id=7, for_update=True)

    assert session is None
    read_sql = _assert_user_lock_first(db)
    assert 'QBANK_V2_PRACTICE_SESSION' in read_sql
    assert 'FOR UPDATE' in read_sql


async def test_get_owned_item_locks_user_before_join_read() -> None:
    """取会话题目写锁时同样先锁用户，再读取会话与投递题目。"""
    db = _RecordingDB()

    context = await practice_session_dao.get_owned_item(
        db,
        session_key='session-123',
        user_id=7,
        session_item_id=21,
        for_update=True,
    )

    assert context is None
    read_sql = _assert_user_lock_first(db)
    assert 'QBANK_V2_PRACTICE_SESSION_ITEM' in read_sql
    assert 'FOR UPDATE' in read_sql


async def test_get_owned_item_include_hidden_still_locks_user_first() -> None:
    """隐藏会话的重试入口同样先锁用户，再锁定会话与投递题目。"""
    db = _RecordingDB()

    context = await practice_session_dao.get_owned_item(
        db,
        session_key='session-123',
        user_id=7,
        session_item_id=21,
        for_update=True,
        include_hidden=True,
    )

    assert context is None
    read_sql = _assert_user_lock_first(db)
    assert 'QBANK_V2_PRACTICE_SESSION_ITEM' in read_sql
    assert 'FOR UPDATE' in read_sql


async def test_evaluation_context_locks_user_before_attempt_read() -> None:
    """评测取作答上下文时用户父锁在前，多表读取不再提前锁题目。"""
    db = _RecordingDB()

    context = await evaluation_run_dao.get_attempt_context(db, attempt_id=41, user_id=7, for_update=True)

    assert context is None
    read_sql = _assert_user_lock_first(db)
    assert 'QBANK_V2_QUESTION_ATTEMPT' in read_sql
    assert 'FOR UPDATE' not in read_sql


class _CreateRecordingDB(_RecordingDB):
    """在记录 SQL 之外，按发生顺序记录 add / flush。"""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[str] = []

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> _EmptyResult:
        self.events.append('lock' if 'FOR UPDATE' in _sql(statement) else 'read')
        return await super().execute(statement, *args, **kwargs)

    def add(self, instance: Any) -> None:
        self.events.append('add')

    async def flush(self) -> None:
        self.events.append('flush')


async def test_create_locks_user_before_insert() -> None:
    """创建会话必须在 INSERT 之前取用户写锁，避免外键共享锁升级死锁。"""
    db = _CreateRecordingDB()

    session = await practice_session_dao.create(db, {'user_id': 7, 'session_key': 'session-123'})

    assert session.user_id == 7
    assert db.events == ['lock', 'add', 'flush']
    user_sql = _sql(db.statements[0])
    assert 'SYS_USER' in user_sql
    assert 'FOR UPDATE' in user_sql


async def test_lock_questions_sorts_and_dedupes_before_for_update() -> None:
    """题目锁按 ID 升序去重后逐条加锁，避免交叉题序死锁。"""
    db = _RecordingDB()

    await AttemptProjectionService.lock_questions(db, [3, 1, 3, 2])

    assert len(db.statements) == 3
    locked_ids: list[int] = []
    for statement in db.statements:
        sql = _sql(statement)
        assert 'QBANK_V2_QUESTION' in sql
        assert 'FOR UPDATE' in sql
        match = re.search(r'QBANK_V2_QUESTION\.ID = (\d+)', sql)
        assert match is not None
        locked_ids.append(int(match.group(1)))
    assert locked_ids == [1, 2, 3]
