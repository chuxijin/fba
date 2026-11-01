"""旧错题导入用时回归。

覆盖既有契约：

1. 内容指纹归一选项前缀、微型箭头/破折号图片、强调与下划线排版；
2. 来源身份优先使用显式 ``source_question_key``，它可以是非数字的原站 globalId（如 ``fb-q1``）；
   只有缺省时才回退 ``external_key``，且该旧格式只接受 ``fenbi:<正整数题号>``；
   ``o1`` 等题序兜底键在任何情况下都不能当稳定身份；
3. ``find_import_question`` 先按内容指纹复用，命中即不再查来源；无可靠身份也不查来源；
   未命中才取 ``find_source_questions`` 的第一条，空结果为 ``None``，底层异常原样抛出；
4. ``find_source_questions`` 按本用户活跃 private 题 + 原站 platform/key + 内容 digest
   从错题元数据或导入作答来源找回同题，兼容旧指纹，且不迁移、不合并旧数据。

所有 DAO 查询都在内存 SQLite 上执行真实 SQL，不连接任何开发或生产环境；
公共分支的调用边界用 AsyncMock 校验，不触碰真实数据库。
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace, TracebackType
from typing import Any
from unittest.mock import AsyncMock

import pytest

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from backend.app.question_bank_v2.crud.crud_external_practice import external_practice_dao
from backend.app.question_bank_v2.crud.crud_practice import question_attempt_dao
from backend.app.question_bank_v2.crud.crud_review import wrong_question_state_dao
from backend.app.question_bank_v2.model.bank import QbBank, QbBankItem, QbBankRevision, QbBankSection
from backend.app.question_bank_v2.model.practice import QbPracticeSession, QbPracticeSessionItem, QbQuestionAttempt
from backend.app.question_bank_v2.model.question import QbQuestion, QbQuestionAnswer, QbQuestionExplanation
from backend.app.question_bank_v2.model.review import QbWrongQuestionState
from backend.app.question_bank_v2.model.statistics import QbUserQuestionMastery
from backend.app.question_bank_v2.schema.external_practice import ImportPracticeQuestionParam
from backend.app.question_bank_v2.schema.review import CreateExternalWrongQuestionParam
from backend.app.question_bank_v2.service import wrong_review_service as review_module
from backend.app.question_bank_v2.service.wrong_review_service import WrongReviewService
from backend.app.question_bank_v2.utils.external_practice import (
    EXTERNAL_PRACTICE_ORIGIN,
    external_question_identity,
    normalize_content_for_digest,
    question_content_digest,
)
from backend.common.exception import errors

USER_ID = 7
OTHER_USER_ID = 8
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)

CORE: dict[str, Any] = {
    'stem': '<p>题干</p>',
    'content_format': 'html',
    'question_type': 'single_choice',
    'options': [
        {'option_code': 'A', 'content': 'A. 选项甲', 'sort_order': 0},
        {'option_code': 'B', 'content': 'B. 选项乙', 'sort_order': 1},
    ],
}
ALTERED_CORE: dict[str, Any] = {
    **CORE,
    'stem': '<p>另一道题干</p>',
}

SQLITE_TABLES = [
    QbBank.__table__,
    QbBankRevision.__table__,
    QbBankSection.__table__,
    QbBankItem.__table__,
    QbQuestion.__table__,
    QbQuestionAnswer.__table__,
    QbQuestionExplanation.__table__,
    QbUserQuestionMastery.__table__,
    QbWrongQuestionState.__table__,
    QbPracticeSession.__table__,
    QbPracticeSessionItem.__table__,
    QbQuestionAttempt.__table__,
]


class _AsyncNestedTransaction:
    """把同步 Session 的 SAVEPOINT 包装成 async 上下文，供业务代码 begin_nested 使用。"""

    def __init__(self, transaction: Any) -> None:
        self._transaction = transaction

    async def __aenter__(self) -> Any:
        return self._transaction.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        return self._transaction.__exit__(exc_type, exc, tb)


def _assign_missing_question_ids(session: Session, flush_context: Any, instances: Any) -> None:
    """内存 SQLite 的 BIGINT 主键不会自增；真实 DAO 建题时补齐主键。"""
    missing = [obj for obj in session.new if isinstance(obj, QbQuestion) and obj.id is None]
    if not missing:
        return
    next_id = session.execute(select(func.coalesce(func.max(QbQuestion.id), 0))).scalar_one()
    for question in missing:
        next_id += 1
        question.id = next_id


class AsyncSQLiteDB:
    """把异步 DAO 调用落到真实的内存 SQLite Session；数据库不落盘。"""

    def __init__(self) -> None:
        self.engine = create_engine('sqlite://')
        for table in SQLITE_TABLES:
            table.create(self.engine)
        self.session = Session(self.engine)
        event.listen(self.session, 'before_flush', _assign_missing_question_ids)

    def get_bind(self) -> Any:
        return self.session.get_bind()

    async def execute(self, stmt: Any) -> Any:
        return self.session.execute(stmt)

    async def scalars(self, stmt: Any) -> Any:
        return self.session.scalars(stmt)

    def add(self, obj: Any) -> None:
        self.session.add(obj)

    async def flush(self) -> None:
        self.session.flush()

    def begin_nested(self) -> _AsyncNestedTransaction:
        return _AsyncNestedTransaction(self.session.begin_nested())

    def commit(self) -> None:
        self.session.commit()

    def close(self) -> None:
        event.remove(self.session, 'before_flush', _assign_missing_question_ids)
        self.session.close()
        self.engine.dispose()


@pytest.fixture
def db() -> Iterator[AsyncSQLiteDB]:
    database = AsyncSQLiteDB()
    yield database
    database.close()


def _seed_question(
    db: AsyncSQLiteDB,
    *,
    question_id: int = 1,
    owner_id: int = USER_ID,
    visibility: str = 'private',
    deleted: int = 0,
    core: dict[str, Any] = CORE,
    content_hash: str | None = None,
) -> int:
    db.session.execute(
        QbQuestion.__table__.insert().values(
            id=question_id,
            code=f'q{question_id}',
            stem=core['stem'],
            owner_id=owner_id,
            visibility=visibility,
            origin_type='imported',
            status='active',
            content_format=core['content_format'],
            question_type=core['question_type'],
            option_data=core['options'],
            default_score=1,
            content_hash=content_hash or question_content_digest(**core),
            created_by=owner_id,
            deleted=deleted,
            created_time=NOW,
        )
    )
    return question_id


def _seed_wrong_state(
    db: AsyncSQLiteDB,
    *,
    state_id: int = 1,
    user_id: int = USER_ID,
    question_id: int = 1,
    platform: str = 'fenbi',
    external_key: str = 'fenbi:paper:123',
    deleted: int = 0,
    review_count: int = 1,
    source_question_key: str | None = None,
) -> int:
    entry_metadata: dict[str, Any] = {
        'source': platform,
        'source_system': platform,
        'external_key': external_key,
        'import_batch_id': 'batch-1234',
        'section_name': '数量关系',
    }
    if source_question_key is not None:
        entry_metadata['source_question_key'] = source_question_key
    db.session.execute(
        QbWrongQuestionState.__table__.insert().values(
            id=state_id,
            user_id=user_id,
            question_id=question_id,
            entry_source='import',
            entry_metadata=entry_metadata,
            status='active',
            wrong_count=1,
            correct_streak=0,
            is_pinned=False,
            review_count=review_count,
            practice_level=0,
            created_by=user_id,
            deleted=deleted,
            created_time=NOW,
        )
    )
    return state_id


def _seed_session(
    db: AsyncSQLiteDB,
    *,
    session_id: int = 10,
    user_id: int = USER_ID,
    platform: str = 'fenbi',
    deleted: int = 0,
) -> int:
    db.session.execute(
        QbPracticeSession.__table__.insert().values(
            id=session_id,
            session_key=f'external-{session_id}',
            user_id=user_id,
            mode='practice',
            source_type='custom',
            source_ref=f'external-practice:{session_id}',
            status='graded',
            started_time=NOW,
            total_items=1,
            answered_items=1,
            correct_items=0,
            score=0,
            delivery_config={},
            source_snapshot={
                'origin': EXTERNAL_PRACTICE_ORIGIN,
                'platform': platform,
                'practice_log_id': session_id,
            },
            deleted=deleted,
            created_time=NOW,
        )
    )
    return session_id


def _seed_attempt(
    db: AsyncSQLiteDB,
    *,
    attempt_id: int,
    question_id: int = 1,
    user_id: int = USER_ID,
    duration_ms: int | None,
    submitted_time: datetime = NOW,
    is_correct: bool = False,
    deleted: int = 0,
    response_data: Any = 'A',
    session_id: int | None = None,
    session_item_id: int | None = None,
    grading_result: dict[str, Any] | None = None,
) -> int:
    db.session.execute(
        QbQuestionAttempt.__table__.insert().values(
            id=attempt_id,
            user_id=user_id,
            question_id=question_id,
            response_data=response_data,
            annotations=[],
            session_id=session_id,
            session_item_id=session_item_id,
            attempt_no=attempt_id,
            is_correct=is_correct,
            duration_ms=duration_ms,
            grading_status='graded',
            grading_method='rule',
            grading_result=grading_result or {},
            submitted_time=submitted_time,
            deleted=deleted,
            created_time=NOW,
        )
    )
    return attempt_id


async def _find_peers(db: AsyncSQLiteDB, *, source_question_key: str = '123', platform: str = 'fenbi') -> list[int]:
    questions = await external_practice_dao.find_source_questions(
        db,
        user_id=USER_ID,
        platform=platform,
        source_question_key=source_question_key,
        core=CORE,
    )
    return [question.id for question in questions]


def _stub_detail_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    """详情只读装配用到的材料/解析查询与本次断言无关。"""
    monkeypatch.setattr(review_module.question_material_dao, 'get_all', AsyncMock(return_value=[]))
    monkeypatch.setattr(review_module.question_explanation_dao, 'get_published_by_question', AsyncMock(return_value=[]))


def _mutation_fingerprint(db: AsyncSQLiteDB) -> tuple[Any, ...]:
    """用于确认详情读取没有写库：题目、错题状态、作答、会话的关键列快照。"""

    def rows(stmt: Any) -> tuple[Any, ...]:
        return tuple(tuple(row) for row in db.session.execute(stmt).all())

    return (
        rows(select(QbQuestion.id, QbQuestion.content_hash, QbQuestion.deleted).order_by(QbQuestion.id)),
        rows(
            select(QbWrongQuestionState.id, QbWrongQuestionState.question_id, QbWrongQuestionState.deleted).order_by(
                QbWrongQuestionState.id
            )
        ),
        rows(
            select(
                QbQuestionAttempt.id,
                QbQuestionAttempt.user_id,
                QbQuestionAttempt.duration_ms,
                QbQuestionAttempt.is_correct,
                QbQuestionAttempt.deleted,
            ).order_by(QbQuestionAttempt.id)
        ),
        rows(
            select(QbPracticeSession.id, QbPracticeSession.user_id, QbPracticeSession.deleted).order_by(
                QbPracticeSession.id
            )
        ),
    )


def _wrong_param(
    *,
    idempotency_key: str = 'wrong-reuse-0001',
    external_key: str = 'fenbi:paper:123',
    entry_metadata: dict[str, Any] | None = None,
) -> CreateExternalWrongQuestionParam:
    return CreateExternalWrongQuestionParam(
        idempotency_key=idempotency_key,
        entry_source='import',
        stem=CORE['stem'],
        content_format='html',
        question_type='single_choice',
        options=CORE['options'],
        answer={'answer_data': {'correct': ['A']}},
        source_system='fenbi',
        external_key=external_key,
        entry_metadata=entry_metadata or {'source': 'fenbi'},
    )


# ---------------------------------------------------------------------------
# 内容指纹与来源身份
# ---------------------------------------------------------------------------


def test_digest_normalizes_option_prefix_layout_and_symbol_images() -> None:
    arrow_tag = '<img src="https://fb.fenbike.cn/fb/22356dff5dbcdc4c37e6632600979a0e.png" style="width:12px">'
    dash_tag = '<img src="https://fb.fenbike.cn/fb/abe086ab947f7a5b37c464c4ce74f115.png">'
    noisy = {
        'stem': f'<p><b>甲</b> {arrow_tag} 乙 {dash_tag} 丙<u> </u>丁&nbsp;戊</p>',
        'content_format': 'html',
        'question_type': 'single_choice',
        'options': [
            {'option_code': 'A', 'content': 'A. 选项甲', 'sort_order': 0},
            {'option_code': 'B', 'content': 'b、选项乙', 'sort_order': 1},
        ],
    }
    clean = {
        'stem': (
            '<p>甲 <img src="https://fb.fenbike.cn/arrow.png"> '
            '乙 <img src="https://fb.fenbike.cn/dash.png"> 丙______丁 戊</p>'
        ),
        'content_format': 'html',
        'question_type': 'single_choice',
        'options': [
            {'option_code': 'A', 'content': '选项甲', 'sort_order': 0},
            {'option_code': 'B', 'content': '选项乙', 'sort_order': 1},
        ],
    }

    assert question_content_digest(**noisy) == question_content_digest(**clean)
    normalized = normalize_content_for_digest(noisy['stem'])
    assert ' → ' in normalized and ' — ' in normalized and '______' in normalized
    assert '<b>' not in normalized and '<u>' not in normalized
    # 内容确实不同时必须产生不同指纹，避免归一化把题目误合并。
    assert question_content_digest(**{**clean, 'stem': '<p>甲 乙 丙 丁 戊</p>'}) != question_content_digest(**clean)


@pytest.mark.parametrize(
    ('metadata', 'expected'),
    [
        ({'source_system': 'fenbi', 'external_key': 'fenbi:123'}, ('fenbi', '123')),
        ({'source_system': 'fenbi', 'external_key': 'fenbi:paper:123'}, ('fenbi', '123')),
        ({'source_system': 'fenbi', 'external_key': 'fenbi:paper:0'}, None),
        ({'source_system': 'fenbi', 'external_key': 'fenbi:paper:-1'}, None),
        ({'source_system': 'fenbi', 'external_key': 'fenbi:o1'}, None),
        ({'source_system': 'fenbi', 'external_key': 'o1'}, None),
        ({'source_system': 'fenbi', 'external_key': 'fenbi:paper:abc'}, None),
        ({'source_system': 'other', 'external_key': 'other:123'}, None),
        (None, None),
    ],
)
def test_external_question_identity_only_accepts_positive_integer_key(
    metadata: dict[str, Any] | None, expected: tuple[str, str] | None
) -> None:
    assert external_question_identity(metadata) == expected


# ---------------------------------------------------------------------------
# find_source_questions：两条来源链路
# ---------------------------------------------------------------------------


async def test_find_source_questions_matches_wrong_state_metadata(db: AsyncSQLiteDB) -> None:
    _seed_question(db)
    _seed_wrong_state(db)
    db.commit()

    assert await _find_peers(db) == [1]


async def test_find_source_questions_matches_external_practice_attempt(db: AsyncSQLiteDB) -> None:
    _seed_question(db)
    _seed_session(db)
    _seed_attempt(
        db,
        attempt_id=100,
        session_id=10,
        session_item_id=1,
        duration_ms=12000,
        grading_result={'origin': EXTERNAL_PRACTICE_ORIGIN, 'source_question_key': '123'},
    )
    db.commit()

    assert await _find_peers(db) == [1]


async def test_ensure_question_reuses_legacy_source_when_hash_misses(db: AsyncSQLiteDB) -> None:
    legacy_hash = '0' * 64
    _seed_question(db, content_hash=legacy_hash)
    _seed_wrong_state(db)
    db.commit()

    question = await external_practice_dao.ensure_question(
        db, user_id=USER_ID, platform='fenbi', item=_practice_param(duration_seconds=None)
    )

    # 精确内容指纹没命中旧行，但来源 + 内容 digest 仍能复用旧题，不新建也不改旧 hash。
    assert question.id == 1
    assert db.session.scalar(select(func.count()).select_from(QbQuestion)) == 1
    assert db.session.scalar(select(QbQuestion.content_hash).where(QbQuestion.id == 1)) == legacy_hash


async def test_reuse_or_create_question_accepts_legacy_peer(db: AsyncSQLiteDB) -> None:
    legacy_hash = '1' * 64
    _seed_question(db, content_hash=legacy_hash)
    _seed_wrong_state(db)
    db.commit()

    obj = CreateExternalWrongQuestionParam(
        idempotency_key='legacy-reuse-0001',
        entry_source='import',
        stem=CORE['stem'],
        content_format='html',
        question_type='single_choice',
        options=CORE['options'],
        answer={'answer_data': {'correct': ['A']}},
        source_system='fenbi',
        external_key='fenbi:paper:123',
        entry_metadata={'source': 'fenbi'},
    )
    question, reused = await WrongReviewService._reuse_or_create_question(db=db, user_id=USER_ID, obj=obj)

    assert reused is True
    assert question.id == 1
    assert db.session.scalar(select(func.count()).select_from(QbQuestion)) == 1


async def test_two_import_orders_converge_on_same_question_and_same_duration() -> None:
    async def build(*, insert_wrong_first: bool) -> tuple[list[int], list[int | None]]:
        database = AsyncSQLiteDB()
        try:
            canonical, duplicate = 1, 2

            def wrong_side() -> None:
                _seed_question(database, question_id=canonical)
                _seed_wrong_state(database, question_id=canonical)
                _seed_attempt(database, attempt_id=200, question_id=canonical, duration_ms=9000, submitted_time=NOW)

            def practice_side() -> None:
                _seed_question(database, question_id=duplicate)
                _seed_session(database)
                _seed_attempt(
                    database,
                    attempt_id=100,
                    question_id=duplicate,
                    duration_ms=12000,
                    submitted_time=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
                    session_id=10,
                    session_item_id=1,
                    grading_result={'origin': EXTERNAL_PRACTICE_ORIGIN, 'source_question_key': '123'},
                )

            if insert_wrong_first:
                wrong_side()
                practice_side()
            else:
                practice_side()
                wrong_side()
            database.commit()

            peers = await _find_peers(database)
            history = await question_attempt_dao.get_wrong_answer_history(
                database,
                user_id=USER_ID,
                question_id=canonical,
                related_question_ids=[question_id for question_id in peers if question_id != canonical],
            )
            return peers, [row['duration_ms'] for row in history]
        finally:
            database.close()

    wrong_first = await build(insert_wrong_first=True)
    practice_first = await build(insert_wrong_first=False)

    # 两种导入顺序都收敛到同一组题目，用时都来自各自那次错误作答记录。
    assert wrong_first == practice_first == ([1, 2], [9000, 12000])


# ---------------------------------------------------------------------------
# find_source_questions：命中边界
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('question_kwargs', 'state_kwargs'),
    [
        ({}, {'platform': 'zhihu', 'external_key': 'zhihu:paper:123'}),
        ({}, {'user_id': OTHER_USER_ID}),
        ({'owner_id': OTHER_USER_ID}, {}),
        ({'core': ALTERED_CORE}, {}),
        ({'visibility': 'internal'}, {}),
        ({'visibility': 'public'}, {}),
        ({'deleted': 1}, {}),
        ({}, {'deleted': 1}),
    ],
    ids=[
        'platform',
        'state-user',
        'question-owner',
        'content',
        'internal',
        'public',
        'question-deleted',
        'state-deleted',
    ],
)
async def test_find_source_questions_rejects_non_matching_candidates(
    db: AsyncSQLiteDB, question_kwargs: dict[str, Any], state_kwargs: dict[str, Any]
) -> None:
    _seed_question(db, **question_kwargs)
    _seed_wrong_state(db, **state_kwargs)
    db.commit()

    assert await _find_peers(db) == []


async def test_external_key_suffix_boundary_does_not_match_1123_as_123(db: AsyncSQLiteDB) -> None:
    _seed_question(db, question_id=1)
    _seed_wrong_state(db, external_key='fenbi:paper:1123')
    db.commit()

    # 只按末尾 `:123` 匹配时会把 1123 误判成同一题；带冒号边界后不应命中。
    assert await _find_peers(db, source_question_key='123') == []
    assert await _find_peers(db, source_question_key='1123') == [1]


# ---------------------------------------------------------------------------
# 历史重复题：只读 peer 用时，不改数据
# ---------------------------------------------------------------------------


async def test_legacy_duplicate_question_durations_are_read_without_mutation(
    db: AsyncSQLiteDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_question(db, question_id=1)
    _seed_question(db, question_id=2)
    _seed_wrong_state(db, question_id=1, review_count=1)
    _seed_attempt(db, attempt_id=101, question_id=1, duration_ms=11000, submitted_time=NOW)
    # 旧版本另一条导入链路为同一原站题留下了重复私有题和独立作答。
    _seed_session(db)
    _seed_attempt(
        db,
        attempt_id=102,
        question_id=2,
        duration_ms=22000,
        submitted_time=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
        session_id=10,
        session_item_id=1,
        grading_result={'origin': EXTERNAL_PRACTICE_ORIGIN, 'source_question_key': '123'},
    )
    db.commit()

    peers = await _find_peers(db)
    assert peers == [1, 2]

    monkeypatch.setattr(review_module.question_material_dao, 'get_all', AsyncMock(return_value=[]))
    monkeypatch.setattr(review_module.question_explanation_dao, 'get_published_by_question', AsyncMock(return_value=[]))
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=1)

    assert [item.duration_ms for item in detail.wrong_answer_history] == [11000, 22000]
    assert detail.last_wrong_duration_ms == 11000

    # 旧重复题只读不合并：题目、作答、错题状态行数和归属都保持原样。
    digest = question_content_digest(**CORE)
    assert db.session.scalar(select(func.count()).select_from(QbQuestion)) == 2
    assert db.session.scalar(select(QbQuestion.content_hash).where(QbQuestion.id == 1)) == digest
    assert db.session.scalar(select(QbWrongQuestionState.question_id).where(QbWrongQuestionState.id == 1)) == 1
    assert db.session.scalar(select(func.count()).select_from(QbQuestionAttempt)) == 2


# ---------------------------------------------------------------------------
# 用时语义：未知保持 None、0 保留 0、最新未知不借旧已知
# ---------------------------------------------------------------------------


async def test_wrong_history_keeps_unknown_none_and_zero_duration(db: AsyncSQLiteDB) -> None:
    _seed_question(db, question_id=1)
    _seed_wrong_state(db, question_id=1, review_count=1)
    _seed_attempt(db, attempt_id=301, question_id=1, duration_ms=None, submitted_time=NOW)
    _seed_attempt(
        db, attempt_id=302, question_id=1, duration_ms=12000, submitted_time=datetime(2026, 9, 30, tzinfo=UTC)
    )
    _seed_attempt(db, attempt_id=303, question_id=1, duration_ms=0, submitted_time=datetime(2026, 9, 29, tzinfo=UTC))
    db.commit()

    history = await question_attempt_dao.get_wrong_answer_history(db, user_id=USER_ID, question_id=1)
    assert [row['duration_ms'] for row in history] == [None, 12000, 0]


async def test_detail_does_not_borrow_old_known_duration_for_latest_unknown(
    db: AsyncSQLiteDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_question(db, question_id=1)
    _seed_wrong_state(db, question_id=1, review_count=1)
    _seed_attempt(db, attempt_id=301, question_id=1, duration_ms=None, submitted_time=NOW)
    _seed_attempt(
        db, attempt_id=302, question_id=1, duration_ms=12000, submitted_time=datetime(2026, 9, 30, tzinfo=UTC)
    )
    _seed_attempt(db, attempt_id=303, question_id=1, duration_ms=0, submitted_time=datetime(2026, 9, 29, tzinfo=UTC))
    db.commit()

    monkeypatch.setattr(review_module.question_material_dao, 'get_all', AsyncMock(return_value=[]))
    monkeypatch.setattr(review_module.question_explanation_dao, 'get_published_by_question', AsyncMock(return_value=[]))
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=1)

    # 最近一次错误记录用时未知，就不能拿上一次的 12000 顶替。
    assert detail.last_wrong_duration_ms is None
    assert [item.duration_ms for item in detail.wrong_answer_history] == [None, 12000, 0]
    assert detail.wrong_answer_history[-1].duration_ms == 0


async def test_save_response_persists_unknown_and_zero_duration_semantics() -> None:
    for duration_seconds in (None, 0):
        collector = _CollectingDB()
        await external_practice_dao.save_response(
            collector,
            session=SimpleNamespace(id=10, user_id=USER_ID, source_snapshot={'practice_log_id': 55}),
            item=SimpleNamespace(id=1, question_id=1),
            data=_practice_param(duration_seconds=duration_seconds),
            occurred_at=NOW,
        )
        response, attempt = collector.added
        if duration_seconds is None:
            assert attempt.duration_ms is None
        else:
            assert attempt.duration_ms == 0
        # 草稿时长列非空，未知时落 0；作答事实保留 null 供详情判断。
        assert response.duration_ms == 0


# ---------------------------------------------------------------------------
# 详情读取与作答历史过滤
# ---------------------------------------------------------------------------


async def test_detail_row_exposes_entry_metadata_for_identity(db: AsyncSQLiteDB) -> None:
    _seed_question(db, question_id=1)
    _seed_wrong_state(db, question_id=1)
    db.commit()

    row = await wrong_question_state_dao.get_detail_row(db, pk=1, user_id=USER_ID)
    assert row is not None
    metadata = row['entry_metadata']
    assert metadata['source_system'] == 'fenbi'
    assert metadata['external_key'] == 'fenbi:paper:123'
    assert external_question_identity(metadata) == ('fenbi', '123')


async def test_wrong_history_defaults_to_one_question_and_always_filters_user(db: AsyncSQLiteDB) -> None:
    _seed_question(db, question_id=1)
    _seed_question(db, question_id=2)
    _seed_attempt(db, attempt_id=401, question_id=1, duration_ms=8000, submitted_time=NOW)
    _seed_attempt(db, attempt_id=402, question_id=1, duration_ms=7000, submitted_time=NOW, is_correct=True)
    _seed_attempt(db, attempt_id=403, question_id=1, duration_ms=6000, submitted_time=NOW, deleted=5)
    _seed_attempt(db, attempt_id=404, question_id=1, duration_ms=5000, submitted_time=NOW, user_id=OTHER_USER_ID)
    _seed_attempt(db, attempt_id=405, question_id=2, duration_ms=4000, submitted_time=NOW)
    _seed_attempt(db, attempt_id=406, question_id=2, duration_ms=3000, submitted_time=NOW, user_id=OTHER_USER_ID)
    db.commit()

    default_history = await question_attempt_dao.get_wrong_answer_history(db, user_id=USER_ID, question_id=1)
    assert [row['attempt_id'] for row in default_history] == [401]

    related_history = await question_attempt_dao.get_wrong_answer_history(
        db, user_id=USER_ID, question_id=1, related_question_ids=[2]
    )
    # 关联题也不能绕过用户过滤：只多出本用户在题 2 上的错误作答。
    assert [row['attempt_id'] for row in related_history] == [405, 401]


# ---------------------------------------------------------------------------
# 真实录入链路：旧状态无作答，后来刷题记录补上真实作答
# ---------------------------------------------------------------------------


async def test_detail_reads_later_practice_attempt_for_legacy_wrong_state(
    db: AsyncSQLiteDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """旧错题只有状态没有作答；后来刷题记录导入的真实作答要能回显答案和用时。"""
    _seed_question(db, question_id=1)
    _seed_wrong_state(db, state_id=1, question_id=1, review_count=1)
    _seed_question(db, question_id=2)
    _seed_session(db, session_id=10)
    _seed_attempt(
        db,
        attempt_id=501,
        question_id=2,
        duration_ms=30000,
        submitted_time=NOW,
        response_data={'selected': ['B']},
        session_id=10,
        session_item_id=1,
        grading_result={'origin': EXTERNAL_PRACTICE_ORIGIN, 'source_question_key': '123'},
    )
    db.commit()

    before = _mutation_fingerprint(db)
    _stub_detail_reads(monkeypatch)
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=1)

    assert detail.question_id == 1
    assert detail.last_wrong_response == {'selected': ['B']}
    assert detail.last_wrong_duration_ms == 30000
    assert [item.answer for item in detail.wrong_answer_history] == [{'selected': ['B']}]
    assert [item.duration_ms for item in detail.wrong_answer_history] == [30000]
    # 详情只读 peer 的既有作答，不重建题目、不写状态、不改作答。
    assert _mutation_fingerprint(db) == before


@pytest.mark.parametrize('duration_seconds', [0, 30])
async def test_real_import_orders_converge_on_one_question_and_duration(
    duration_seconds: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """两种导入顺序分别真实建题/复用，最终只留一道题，详情用时一致。"""

    async def build(*, wrong_first: bool) -> tuple[Any, ...]:
        database = AsyncSQLiteDB()
        try:
            wrong_param = _wrong_param()
            practice_item = _practice_param(duration_seconds=duration_seconds)
            expected_duration_ms = duration_seconds * 1000

            async def wrong_side() -> None:
                # 错题录入侧真实走 _reuse_or_create_question，但不产生作答事实。
                question, _ = await WrongReviewService._reuse_or_create_question(
                    db=database, user_id=USER_ID, obj=wrong_param
                )
                _seed_wrong_state(database, state_id=1, question_id=question.id, review_count=1)

            async def practice_side() -> None:
                # 刷题记录侧真实走 ensure_question，并落一条会话内作答。
                question = await external_practice_dao.ensure_question(
                    database, user_id=USER_ID, platform='fenbi', item=practice_item
                )
                _seed_session(database, session_id=10)
                _seed_attempt(
                    database,
                    attempt_id=501,
                    question_id=question.id,
                    duration_ms=expected_duration_ms,
                    submitted_time=NOW,
                    session_id=10,
                    session_item_id=1,
                    grading_result={'origin': EXTERNAL_PRACTICE_ORIGIN, 'source_question_key': '123'},
                )

            if wrong_first:
                await wrong_side()
                await practice_side()
            else:
                await practice_side()
                await wrong_side()
            database.commit()

            question_count = database.session.scalar(select(func.count()).select_from(QbQuestion))
            _stub_detail_reads(monkeypatch)
            detail = await WrongReviewService.get_detail(db=database, user_id=USER_ID, wrong_state_id=1)
            return (
                question_count,
                detail.question_id,
                detail.last_wrong_duration_ms,
                tuple(item.duration_ms for item in detail.wrong_answer_history),
            )
        finally:
            database.close()

    wrong_first = await build(wrong_first=True)
    practice_first = await build(wrong_first=False)

    assert wrong_first == practice_first
    assert wrong_first[0] == 1
    assert wrong_first[2] == duration_seconds * 1000
    assert wrong_first[3] == (duration_seconds * 1000,)


# ---------------------------------------------------------------------------
# 显式原站题号：raw globalId 优先于数值 external_key
# ---------------------------------------------------------------------------


def test_explicit_source_question_key_accepts_raw_global_id() -> None:
    metadata = {
        'source_system': 'fenbi',
        'external_key': 'fenbi:paper:123',
        'source_question_key': 'fb-q1',
    }
    assert external_question_identity(metadata) == ('fenbi', 'fb-q1')
    # 旧的 external_key 仍只接受正整数，不能反推出非数字 globalId。
    assert external_question_identity({'source_system': 'fenbi', 'external_key': 'fenbi:fb-q1'}) is None
    assert external_question_identity({'source_system': 'fenbi', 'external_key': 'fenbi:o1'}) is None


async def test_find_source_questions_matches_explicit_source_question_key(db: AsyncSQLiteDB) -> None:
    _seed_question(db, question_id=1)
    _seed_wrong_state(db, state_id=1, question_id=1, source_question_key='fb-q1')
    _seed_question(db, question_id=2)
    _seed_wrong_state(db, state_id=2, question_id=2, source_question_key='fb-q2')
    db.commit()

    assert await _find_peers(db, source_question_key='fb-q1') == [1]
    assert await _find_peers(db, source_question_key='fb-q2') == [2]
    assert await _find_peers(db, source_question_key='fb-q3') == []


async def test_ensure_question_reuses_legacy_question_by_explicit_source_key(db: AsyncSQLiteDB) -> None:
    legacy_hash = '0' * 64
    _seed_question(db, question_id=1, content_hash=legacy_hash)
    _seed_wrong_state(db, state_id=1, question_id=1, source_question_key='fb-q1')
    db.commit()

    question = await external_practice_dao.ensure_question(
        db,
        user_id=USER_ID,
        platform='fenbi',
        item=_practice_param(duration_seconds=None, source_question_key='fb-q1'),
    )

    assert question.id == 1
    assert db.session.scalar(select(func.count()).select_from(QbQuestion)) == 1
    assert db.session.scalar(select(QbQuestion.content_hash).where(QbQuestion.id == 1)) == legacy_hash


async def test_explicit_source_key_rejects_foreign_user_other_content_and_order_fallback(db: AsyncSQLiteDB) -> None:
    _seed_question(db, question_id=1)
    _seed_wrong_state(db, state_id=1, question_id=1, user_id=OTHER_USER_ID, source_question_key='fb-q1')
    _seed_question(db, question_id=2, core=ALTERED_CORE)
    _seed_wrong_state(db, state_id=2, question_id=2, source_question_key='fb-q1')
    _seed_question(db, question_id=3)
    _seed_wrong_state(db, state_id=3, question_id=3, external_key='fenbi:o1')
    db.commit()

    assert await _find_peers(db, source_question_key='fb-q1') == []
    # 旧 o1 题序不能当稳定身份，非数字显式键也不会走数值兜底。
    assert await _find_peers(db, source_question_key='o1') == []
    assert external_question_identity({'source_system': 'fenbi', 'external_key': 'fenbi:o1'}) is None


# ---------------------------------------------------------------------------
# 选项前缀归一化：数学运算式保留首字母
# ---------------------------------------------------------------------------


def _option_digest(content: str) -> str:
    return question_content_digest(
        stem=CORE['stem'],
        content_format='html',
        question_type='single_choice',
        options=[{'option_code': 'A', 'content': content, 'sort_order': 0}],
    )


@pytest.mark.parametrize('expression', ['A + B', 'A  + B', 'A+B', 'A / B', 'A = B', 'A > B', 'A×B', 'A - B'])
def test_math_expression_option_is_not_stripped_as_option_prefix(expression: str) -> None:
    # “A + B”里的 A 是运算项，不是选项前缀；不能与去掉首字母后的内容同指纹。
    assert _option_digest(expression) != _option_digest(expression[1:].strip())


def test_math_plus_option_does_not_equal_stripped_plus_option() -> None:
    assert _option_digest('A + B') != _option_digest('+ B')
    # 真实选项前缀仍然归一，避免正常前缀被保留进指纹。
    assert _option_digest('A. 选项甲') == _option_digest('选项甲')
    assert _option_digest('A、选项甲') == _option_digest('选项甲')


# ---------------------------------------------------------------------------
# 复盘关联：legacy peer 作答可用，非匹配和他人作答拒绝
# ---------------------------------------------------------------------------


async def test_resolve_review_source_accepts_legacy_peer_attempt(db: AsyncSQLiteDB) -> None:
    _seed_question(db, question_id=1)
    _seed_wrong_state(db, state_id=1, question_id=1)
    _seed_question(db, question_id=2)
    _seed_session(db, session_id=10)
    _seed_attempt(
        db,
        attempt_id=601,
        question_id=2,
        duration_ms=12000,
        submitted_time=NOW,
        response_data='B',
        session_id=10,
        session_item_id=1,
        grading_result={'origin': EXTERNAL_PRACTICE_ORIGIN, 'source_question_key': '123'},
    )
    db.commit()

    wrong_state = await wrong_question_state_dao.get(db, 1, user_id=USER_ID)
    assert wrong_state is not None
    source_attempt, bank_item_id = await WrongReviewService._resolve_review_source(
        db=db,
        user_id=USER_ID,
        wrong_state=wrong_state,
        source_attempt_id=601,
    )

    assert source_attempt is not None
    assert source_attempt.id == 601
    assert source_attempt.question_id == 2
    assert bank_item_id is None


async def test_resolve_review_source_rejects_unmatched_and_foreign_attempts(db: AsyncSQLiteDB) -> None:
    _seed_question(db, question_id=1)
    _seed_wrong_state(db, state_id=1, question_id=1)
    _seed_question(db, question_id=2)
    _seed_session(db, session_id=10)
    _seed_attempt(
        db,
        attempt_id=601,
        question_id=2,
        duration_ms=12000,
        submitted_time=NOW,
        session_id=10,
        session_item_id=1,
        grading_result={'origin': EXTERNAL_PRACTICE_ORIGIN, 'source_question_key': '123'},
    )
    # 同一道 peer 题，但作答属于其他用户。
    _seed_attempt(
        db,
        attempt_id=602,
        question_id=2,
        duration_ms=9000,
        submitted_time=NOW,
        user_id=OTHER_USER_ID,
        session_id=10,
        session_item_id=1,
        grading_result={'origin': EXTERNAL_PRACTICE_ORIGIN, 'source_question_key': '123'},
    )
    # 同用户同内容，但没有任何来源关联的另一道题。
    _seed_question(db, question_id=3)
    _seed_attempt(db, attempt_id=603, question_id=3, duration_ms=8000, submitted_time=NOW)
    # 同用户且来源题号相同，但内容不同的另一道题。
    _seed_question(db, question_id=4, core=ALTERED_CORE)
    _seed_attempt(
        db,
        attempt_id=604,
        question_id=4,
        duration_ms=7000,
        submitted_time=NOW,
        session_id=10,
        session_item_id=1,
        grading_result={'origin': EXTERNAL_PRACTICE_ORIGIN, 'source_question_key': '123'},
    )
    db.commit()

    wrong_state = await wrong_question_state_dao.get(db, 1, user_id=USER_ID)
    assert wrong_state is not None
    for attempt_id in (602, 603, 604):
        with pytest.raises(errors.NotFoundError):
            await WrongReviewService._resolve_review_source(
                db=db,
                user_id=USER_ID,
                wrong_state=wrong_state,
                source_attempt_id=attempt_id,
            )


# ---------------------------------------------------------------------------
# 公共分支：find_import_question / _get_external_source_peers 的调用边界
# ---------------------------------------------------------------------------


def _stub_import_lookups(monkeypatch: pytest.MonkeyPatch, *, reusable: AsyncMock, source: AsyncMock) -> None:
    monkeypatch.setattr(external_practice_dao, 'find_reusable_question', reusable)
    monkeypatch.setattr(external_practice_dao, 'find_source_questions', source)


async def test_find_import_question_prefers_fingerprint_without_source_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = object()
    fingerprint_hit = SimpleNamespace(id=41)
    reusable = AsyncMock(return_value=fingerprint_hit)
    source = AsyncMock(return_value=[SimpleNamespace(id=99)])
    _stub_import_lookups(monkeypatch, reusable=reusable, source=source)

    question = await external_practice_dao.find_import_question(
        db, user_id=USER_ID, core=CORE, identity=('fenbi', 'fb-q1')
    )

    # 指纹命中即短路：来源查询一次都不应发生，即便可靠身份存在。
    assert question is fingerprint_hit
    reusable.assert_awaited_once_with(db, user_id=USER_ID, content_hash=question_content_digest(**CORE))
    source.assert_not_awaited()


async def test_find_import_question_skips_source_lookup_without_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = object()
    reusable = AsyncMock(return_value=None)
    source = AsyncMock(return_value=[SimpleNamespace(id=99)])
    _stub_import_lookups(monkeypatch, reusable=reusable, source=source)

    question = await external_practice_dao.find_import_question(db, user_id=USER_ID, core=CORE, identity=None)

    assert question is None
    reusable.assert_awaited_once()
    source.assert_not_awaited()


async def test_find_import_question_returns_first_source_match(monkeypatch: pytest.MonkeyPatch) -> None:
    db = object()
    first, second = SimpleNamespace(id=11), SimpleNamespace(id=12)
    reusable = AsyncMock(return_value=None)
    source = AsyncMock(return_value=[first, second])
    _stub_import_lookups(monkeypatch, reusable=reusable, source=source)

    question = await external_practice_dao.find_import_question(
        db, user_id=USER_ID, core=CORE, identity=('fenbi', '123')
    )

    assert question is first
    source.assert_awaited_once_with(db, user_id=USER_ID, platform='fenbi', source_question_key='123', core=CORE)


async def test_find_import_question_returns_none_for_empty_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = object()
    reusable = AsyncMock(return_value=None)
    source = AsyncMock(return_value=[])
    _stub_import_lookups(monkeypatch, reusable=reusable, source=source)

    question = await external_practice_dao.find_import_question(
        db, user_id=USER_ID, core=CORE, identity=('fenbi', 'fb-q9')
    )

    assert question is None
    source.assert_awaited_once_with(db, user_id=USER_ID, platform='fenbi', source_question_key='fb-q9', core=CORE)


async def test_find_import_question_propagates_fingerprint_error(monkeypatch: pytest.MonkeyPatch) -> None:
    db = object()
    reusable = AsyncMock(side_effect=RuntimeError('fingerprint lookup down'))
    source = AsyncMock(return_value=[SimpleNamespace(id=1)])
    _stub_import_lookups(monkeypatch, reusable=reusable, source=source)

    with pytest.raises(RuntimeError, match='fingerprint lookup down'):
        await external_practice_dao.find_import_question(db, user_id=USER_ID, core=CORE, identity=('fenbi', '123'))
    # 指纹查询异常不能被吞掉后退化成来源查询，否则会掩盖真实故障。
    source.assert_not_awaited()


async def test_find_import_question_propagates_source_lookup_error(monkeypatch: pytest.MonkeyPatch) -> None:
    db = object()
    reusable = AsyncMock(return_value=None)
    source = AsyncMock(side_effect=RuntimeError('source lookup down'))
    _stub_import_lookups(monkeypatch, reusable=reusable, source=source)

    with pytest.raises(RuntimeError, match='source lookup down'):
        await external_practice_dao.find_import_question(db, user_id=USER_ID, core=CORE, identity=('fenbi', '123'))
    # 来源查询失败必须原样抛出，不能当作“没找到”返回 None 去新建重复题。
    source.assert_awaited_once()


async def test_get_external_source_peers_skips_query_without_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = AsyncMock(return_value=[SimpleNamespace(id=1)])
    monkeypatch.setattr(external_practice_dao, 'find_source_questions', source)

    peers = await WrongReviewService._get_external_source_peers(db=object(), user_id=USER_ID, identity=None, core=CORE)

    assert peers == []
    source.assert_not_awaited()


async def test_get_external_source_peers_forwards_reliable_identity_verbatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = object()
    expected = [SimpleNamespace(id=71), SimpleNamespace(id=72)]
    source = AsyncMock(return_value=expected)
    monkeypatch.setattr(external_practice_dao, 'find_source_questions', source)

    peers = await WrongReviewService._get_external_source_peers(
        db=db, user_id=USER_ID, identity=('fenbi', 'fb-q1'), core=CORE
    )

    # 显式非数字原站题号也要原样转给同一个来源 DAO，不做数值化或改写。
    assert peers is expected
    source.assert_awaited_once_with(db, user_id=USER_ID, platform='fenbi', source_question_key='fb-q1', core=CORE)


# ---------------------------------------------------------------------------
# 辅助对象
# ---------------------------------------------------------------------------


class _EmptyScalarResult:
    def first(self) -> None:
        return None


class _CollectingDB:
    """只收集 save_response 新增对象，不触碰任何数据库。"""

    def __init__(self) -> None:
        self.added: list[Any] = []

    async def scalars(self, stmt: Any) -> Any:
        return _EmptyScalarResult()

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None


def _practice_param(*, duration_seconds: int | None, source_question_key: str = '123') -> ImportPracticeQuestionParam:
    return ImportPracticeQuestionParam(
        source_question_key=source_question_key,
        position=1,
        module_path=['数量关系'],
        stem='<p>题干</p>',
        content_format='html',
        question_type='single_choice',
        options=[
            {'option_code': 'A', 'content': 'A. 选项甲', 'sort_order': 0},
            {'option_code': 'B', 'content': 'B. 选项乙', 'sort_order': 1},
        ],
        status='wrong',
        response_data='A',
        duration_seconds=duration_seconds,
    )
