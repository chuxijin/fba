import asyncio

from datetime import datetime, time, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.admin.model.message import Message, MessageTargetType, MessageType
from backend.app.admin.model.user import User
from backend.app.question_bank_v2.model.bank import QbBank, QbBankItem, QbBankRevision, QbBankSection
from backend.app.question_bank_v2.model.knowledge import QbKnowledgePoint
from backend.app.question_bank_v2.model.material import (
    QbMaterial,
    QbMaterialAnchor,
    QbMaterialRevision,
    QbQuestionInteraction,
    QbQuestionInteractionCandidate,
    QbQuestionMaterial,
)
from backend.app.question_bank_v2.model.practice import (
    QbPracticeSession,
    QbPracticeSessionItem,
    QbPracticeSessionResponse,
    QbQuestionAttempt,
)
from backend.app.question_bank_v2.model.question import QbQuestion, QbQuestionAnswer
from backend.app.question_bank_v2.model.review import (
    QbQuestionReview,
    QbQuestionReviewKnowledgePoint,
    QbQuestionReviewTag,
    QbReviewTag,
    QbWrongQuestionState,
)
from backend.app.question_bank_v2.model.user import QbUserPracticePreference
from backend.app.question_bank_v2.schema.practice import CreatePracticeSessionParam
from backend.app.question_bank_v2.service.notification_service import (
    BIZ_SOURCE,
    RECALL_ACTION,
    qbank_notification_service,
)
from backend.app.question_bank_v2.service.practice_service import practice_service
from backend.common.exception import errors
from backend.common.model import Base

if TYPE_CHECKING:
    from backend.app.admin.schema.message import PublishMessageParam


class MockScalarsResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items


@pytest.mark.asyncio
async def test_notify_practice_due_switch_disabled() -> None:
    """提醒开关未开启时不发提醒"""
    db = AsyncMock()
    pref = SimpleNamespace(
        user_id=1,
        deleted=0,
        review_reminder_enabled=False,
        review_reminder_timezone='Asia/Shanghai',
        review_reminder_time=time(20, 0),
        review_daily_limit=20,
    )
    db.scalar.return_value = pref

    lock_path = 'backend.app.question_bank_v2.service.notification_service.lock_practice_user'
    with patch(lock_path, new=AsyncMock()):
        sent = await qbank_notification_service.notify_practice_due(
            db=db, user_id=1, now=datetime(2026, 11, 2, 21, 0, tzinfo=ZoneInfo('Asia/Shanghai'))
        )
    assert sent is False


@pytest.mark.asyncio
async def test_notify_practice_due_before_reminder_time() -> None:
    """本地时区尚未到达设定的提醒时间时不发提醒"""
    db = AsyncMock()
    pref = SimpleNamespace(
        user_id=1,
        deleted=0,
        review_reminder_enabled=True,
        review_reminder_timezone='Asia/Shanghai',
        review_reminder_time=time(20, 0),
        review_daily_limit=20,
    )
    db.scalar.return_value = pref

    lock_path = 'backend.app.question_bank_v2.service.notification_service.lock_practice_user'
    with patch(lock_path, new=AsyncMock()):
        sent = await qbank_notification_service.notify_practice_due(
            db=db, user_id=1, now=datetime(2026, 11, 2, 19, 30, tzinfo=ZoneInfo('Asia/Shanghai'))
        )
    assert sent is False


@pytest.mark.asyncio
async def test_notify_practice_due_same_day_dedup() -> None:
    """同日已发过消息则幂等不发"""
    db = AsyncMock()
    pref = SimpleNamespace(
        user_id=1,
        deleted=0,
        review_reminder_enabled=True,
        review_reminder_timezone='Asia/Shanghai',
        review_reminder_time=time(20, 0),
        review_daily_limit=20,
    )
    db.scalar.side_effect = [pref, 999]

    lock_path = 'backend.app.question_bank_v2.service.notification_service.lock_practice_user'
    with patch(lock_path, new=AsyncMock()):
        sent = await qbank_notification_service.notify_practice_due(
            db=db, user_id=1, now=datetime(2026, 11, 2, 20, 30, tzinfo=ZoneInfo('Asia/Shanghai'))
        )
    assert sent is False


@pytest.mark.asyncio
async def test_notify_practice_due_success_payload_and_link() -> None:
    """成功发送提醒，payload固定题目批次，link_url带有recallMessageId与mode"""
    db = AsyncMock()
    pref = SimpleNamespace(
        user_id=1,
        deleted=0,
        review_reminder_enabled=True,
        review_reminder_timezone='Asia/Shanghai',
        review_reminder_time=time(20, 0),
        review_daily_limit=10,
    )
    # db.scalar side_effect 顺序：
    # 1. 查询 preference
    # 2. 查询 biz_id 是否已发送 (None)
    # 3. _unfinished 查询 (None)
    db.scalar.side_effect = [pref, None, None]
    db.scalars.return_value = MockScalarsResult([101, 102])

    fake_msg = SimpleNamespace(id=888, link_url=None)
    mock_publish = AsyncMock(return_value=fake_msg)
    now = datetime(2026, 11, 2, 20, 30, tzinfo=ZoneInfo('Asia/Shanghai'))

    lock_path = 'backend.app.question_bank_v2.service.notification_service.lock_practice_user'
    pub_path = 'backend.app.question_bank_v2.service.notification_service.message_service.publish'
    with patch(lock_path, new=AsyncMock()), patch(pub_path, new=mock_publish):
        sent = await qbank_notification_service.notify_practice_due(db=db, user_id=1, now=now)

    assert sent is True
    assert fake_msg.link_url == '/pkg/practice/session/index?recallMessageId=888&mode=practice'
    assert db.flush.called

    mock_publish.assert_called_once()
    published_obj: PublishMessageParam = mock_publish.call_args.kwargs['obj']
    assert published_obj.target_type == MessageTargetType.USER
    assert published_obj.user_id == 1
    assert published_obj.message_type == MessageType.PERSONAL
    assert published_obj.biz_source == BIZ_SOURCE
    assert published_obj.biz_id == 'practice_due:1:2026-11-02'
    assert published_obj.payload['action'] == RECALL_ACTION
    assert published_obj.payload['question_ids'] == [101, 102]
    assert published_obj.payload['due_before'] == now.isoformat()
    assert published_obj.payload['session_key'] is None
    assert published_obj.payload['due_count'] == 2
    assert 'batch_size' not in published_obj.payload


@pytest.mark.asyncio
async def test_open_practice_own_message_success() -> None:
    """读取自己的消息并成功创建练习会话，写入delivery_config"""
    db = AsyncMock()
    user_id = 1
    message_id = 888
    message = SimpleNamespace(
        id=message_id,
        user_id=user_id,
        biz_source=BIZ_SOURCE,
        payload={
            'action': RECALL_ACTION,
            'question_ids': [101, 102],
            'due_before': '2026-11-02T20:30:00+08:00',
            'session_key': None,
        },
    )

    db.scalar.side_effect = [None, None]
    db.scalars.return_value = MockScalarsResult([101, 102])

    created_detail = SimpleNamespace(session_key='recall-message-888')
    practice_session_obj = SimpleNamespace(id=12, session_key='recall-message-888', delivery_config={})
    final_detail = SimpleNamespace(session_key='recall-message-888', total_items=2)

    lock_p = 'backend.app.question_bank_v2.service.notification_service.lock_practice_user'
    msg_p = 'backend.app.question_bank_v2.service.notification_service.message_dao.get_for_user'
    create_p = 'backend.app.question_bank_v2.service.practice_service.practice_service.create'
    get_dao_p = 'backend.app.question_bank_v2.service.notification_service.practice_session_dao.get_by_key'
    get_svc_p = 'backend.app.question_bank_v2.service.practice_service.practice_service.get'

    with (
        patch(lock_p, new=AsyncMock()),
        patch(msg_p, new=AsyncMock(return_value=message)),
        patch(create_p, new=AsyncMock(return_value=created_detail)),
        patch(get_dao_p, new=AsyncMock(return_value=practice_session_obj)),
        patch(get_svc_p, new=AsyncMock(return_value=final_detail)),
    ):
        detail = await qbank_notification_service.open_practice(db=db, user_id=user_id, message_id=message_id)

    assert detail == final_detail
    assert practice_session_obj.delivery_config['recall_message_id'] == message_id
    assert db.flush.called


@pytest.mark.asyncio
async def test_open_practice_cross_user_forbidden() -> None:
    """跨账号访问他人的回测消息或不存在的消息被拒绝 (NotFoundError)"""
    db = AsyncMock()
    lock_p = 'backend.app.question_bank_v2.service.notification_service.lock_practice_user'
    msg_p = 'backend.app.question_bank_v2.service.notification_service.message_dao.get_for_user'

    with patch(lock_p, new=AsyncMock()), patch(msg_p, new=AsyncMock(return_value=None)):
        with pytest.raises(errors.NotFoundError, match='回测消息不存在或不可访问'):
            await qbank_notification_service.open_practice(db=db, user_id=2, message_id=888)

    other_msg = SimpleNamespace(
        id=888,
        user_id=1,
        biz_source=BIZ_SOURCE,
        payload={'action': RECALL_ACTION},
    )
    with patch(lock_p, new=AsyncMock()), patch(msg_p, new=AsyncMock(return_value=other_msg)):
        with pytest.raises(errors.NotFoundError, match='回测消息不存在或不可访问'):
            await qbank_notification_service.open_practice(db=db, user_id=2, message_id=888)


@pytest.mark.asyncio
async def test_open_practice_no_remaining_questions_conflict() -> None:
    """无剩余题冲突：批次中的题若已在其他入口回测或已暂停/失效，无题可练时拒绝 (ConflictError)"""
    db = AsyncMock()
    user_id = 1
    message_id = 888
    message = SimpleNamespace(
        id=message_id,
        user_id=user_id,
        biz_source=BIZ_SOURCE,
        payload={
            'action': RECALL_ACTION,
            'question_ids': [101, 102],
            'due_before': '2026-11-02T20:30:00+08:00',
            'session_key': None,
        },
    )
    db.scalar.side_effect = [None, None]
    db.scalars.return_value = MockScalarsResult([])

    lock_p = 'backend.app.question_bank_v2.service.notification_service.lock_practice_user'
    msg_p = 'backend.app.question_bank_v2.service.notification_service.message_dao.get_for_user'
    with patch(lock_p, new=AsyncMock()), patch(msg_p, new=AsyncMock(return_value=message)):
        with pytest.raises(errors.ConflictError, match='本次提醒中已没有符合条件的已复盘到期题'):
            await qbank_notification_service.open_practice(db=db, user_id=user_id, message_id=message_id)


@pytest.mark.asyncio
async def test_open_practice_reuse_existing_session() -> None:
    """重复点击已有会话续接，不再创建新练习"""
    db = AsyncMock()
    user_id = 1
    message_id = 888
    message = SimpleNamespace(
        id=message_id,
        user_id=user_id,
        biz_source=BIZ_SOURCE,
        payload={
            'action': RECALL_ACTION,
            'question_ids': [101, 102],
            'due_before': '2026-11-02T20:30:00+08:00',
            'session_key': None,
        },
    )
    existing_session = SimpleNamespace(
        id=12,
        user_id=user_id,
        session_key='recall-message-888',
        status='in_progress',
        deleted=0,
        delivery_config={},
    )
    db.scalar.return_value = existing_session

    mock_get = AsyncMock(return_value=SimpleNamespace(session_key='recall-message-888'))
    mock_create = AsyncMock()

    lock_p = 'backend.app.question_bank_v2.service.notification_service.lock_practice_user'
    msg_p = 'backend.app.question_bank_v2.service.notification_service.message_dao.get_for_user'
    get_dao_p = 'backend.app.question_bank_v2.service.notification_service.practice_session_dao.get_by_key'
    get_p = 'backend.app.question_bank_v2.service.practice_service.practice_service.get'
    create_p = 'backend.app.question_bank_v2.service.practice_service.practice_service.create'
    include_p = (
        'backend.app.question_bank_v2.service.notification_service.QbankNotificationService._include_due_questions'
    )

    with (
        patch(lock_p, new=AsyncMock()),
        patch(msg_p, new=AsyncMock(return_value=message)),
        patch(get_dao_p, new=AsyncMock(return_value=existing_session)),
        patch(get_p, new=mock_get),
        patch(create_p, new=mock_create),
        patch(include_p, new=AsyncMock()),
    ):
        res = await qbank_notification_service.open_practice(db=db, user_id=user_id, message_id=message_id)

    assert res.session_key == 'recall-message-888'
    mock_create.assert_not_called()
    mock_get.assert_called_once_with(db=db, session_key='recall-message-888', user_id=user_id)


@pytest.mark.asyncio
async def test_open_practice_hidden_session_not_recreated() -> None:
    """已隐藏/逻辑删除的会话不重新创建，抛出 ConflictError"""
    db = AsyncMock()
    user_id = 1
    message_id = 888
    message = SimpleNamespace(
        id=message_id,
        user_id=user_id,
        biz_source=BIZ_SOURCE,
        payload={
            'action': RECALL_ACTION,
            'question_ids': [101, 102],
            'due_before': '2026-11-02T20:30:00+08:00',
            'session_key': None,
        },
    )
    existing_session = SimpleNamespace(
        id=12,
        user_id=user_id,
        session_key='recall-message-888',
        deleted=1,
    )
    db.scalar.return_value = existing_session

    lock_p = 'backend.app.question_bank_v2.service.notification_service.lock_practice_user'
    msg_p = 'backend.app.question_bank_v2.service.notification_service.message_dao.get_for_user'
    get_dao_p = 'backend.app.question_bank_v2.service.notification_service.practice_session_dao.get_by_key'
    create_p = 'backend.app.question_bank_v2.service.practice_service.practice_service.create'
    with (
        patch(lock_p, new=AsyncMock()),
        patch(msg_p, new=AsyncMock(return_value=message)),
        patch(get_dao_p, new=AsyncMock(return_value=None)),
        patch(create_p, new=AsyncMock()) as mock_create,
    ):
        with pytest.raises(errors.ConflictError, match='这次回测已从练习记录移除，请使用新的回测提醒'):
            await qbank_notification_service.open_practice(db=db, user_id=user_id, message_id=message_id)
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_open_practice_cross_day_unfinished_session_reuse() -> None:
    """跨日未完成会话不重复创建：若存在未完成回测会话，打开新消息时续接未完成会话并回写 message.payload"""
    db = AsyncMock()
    user_id = 1
    message_id = 999
    message = SimpleNamespace(
        id=message_id,
        user_id=user_id,
        biz_source=BIZ_SOURCE,
        payload={
            'action': RECALL_ACTION,
            'question_ids': [101, 102],
            'due_before': '2026-11-03T20:30:00+08:00',
            'session_key': None,
        },
    )

    unfinished_session = SimpleNamespace(
        id=55,
        user_id=user_id,
        session_key='recall-message-888',
        status='in_progress',
        answered_items=1,
        total_items=2,
        deleted=0,
        delivery_config={},
    )
    db.scalar.side_effect = [None, unfinished_session]

    mock_get = AsyncMock(return_value=SimpleNamespace(session_key='recall-message-888'))
    mock_create = AsyncMock()

    lock_p = 'backend.app.question_bank_v2.service.notification_service.lock_practice_user'
    msg_p = 'backend.app.question_bank_v2.service.notification_service.message_dao.get_for_user'
    get_dao_p = 'backend.app.question_bank_v2.service.notification_service.practice_session_dao.get_by_key'
    get_p = 'backend.app.question_bank_v2.service.practice_service.practice_service.get'
    create_p = 'backend.app.question_bank_v2.service.practice_service.practice_service.create'
    include_p = (
        'backend.app.question_bank_v2.service.notification_service.QbankNotificationService._include_due_questions'
    )

    with (
        patch(lock_p, new=AsyncMock()),
        patch(msg_p, new=AsyncMock(return_value=message)),
        patch(get_dao_p, new=AsyncMock(return_value=unfinished_session)),
        patch(get_p, new=mock_get),
        patch(create_p, new=mock_create),
        patch(include_p, new=AsyncMock()),
    ):
        res = await qbank_notification_service.open_practice(db=db, user_id=user_id, message_id=message_id)

    assert res.session_key == 'recall-message-888'
    assert message.payload['session_key'] == 'recall-message-888'
    assert db.flush.called
    mock_create.assert_not_called()
    mock_get.assert_called_once_with(db=db, session_key='recall-message-888', user_id=user_id)


# ==============================================================================
# 真实 SQLite 隔离表测试：验证 _eligible / _unfinished / candidate_users 查询及真实 service 调用
# ==============================================================================


class _SyncSessionAsAsync:
    """包装同步 Session 供异步查询使用"""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        return self._session.execute(statement, *args, **kwargs)

    async def scalar(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        return self._session.scalar(statement, *args, **kwargs)

    async def scalars(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        return self._session.scalars(statement, *args, **kwargs)

    async def flush(self) -> None:
        self._session.flush()

    def add(self, instance: Any) -> None:
        self._session.add(instance)

    def add_all(self, instances: Any) -> None:
        self._session.add_all(instances)


def _init_sqlite_engine() -> Engine:
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            QbBank.__table__,
            QbBankRevision.__table__,
            QbBankSection.__table__,
            QbBankItem.__table__,
            QbQuestion.__table__,
            QbQuestionAnswer.__table__,
            QbMaterial.__table__,
            QbMaterialRevision.__table__,
            QbQuestionMaterial.__table__,
            QbMaterialAnchor.__table__,
            QbQuestionInteraction.__table__,
            QbQuestionInteractionCandidate.__table__,
            QbKnowledgePoint.__table__,
            QbQuestionReview.__table__,
            QbReviewTag.__table__,
            QbQuestionReviewTag.__table__,
            QbQuestionReviewKnowledgePoint.__table__,
            QbWrongQuestionState.__table__,
            QbPracticeSession.__table__,
            QbPracticeSessionItem.__table__,
            QbPracticeSessionResponse.__table__,
            QbQuestionAttempt.__table__,
            QbUserPracticePreference.__table__,
            Message.__table__,
        ],
    )
    return engine


def _make_question(
    id_: int,
    code: str,
    stem: str,
    visibility: str = 'public',
    status: str = 'active',
    owner_id: int | None = None,
    deleted: int = 0,
) -> QbQuestion:
    q = QbQuestion(code=code, stem=stem, visibility=visibility, status=status, owner_id=owner_id, created_by=1)
    q.id = id_
    q.deleted = deleted
    return q


def _make_state(
    id_: int,
    user_id: int,
    question_id: int,
    status: str = 'active',
    next_practice_time: Any = None,
    review_count: int = 1,
    deleted: int = 0,
) -> QbWrongQuestionState:
    st = QbWrongQuestionState(
        user_id=user_id,
        question_id=question_id,
        status=status,
        next_practice_time=next_practice_time,
        review_count=review_count,
        created_by=user_id,
    )
    st.id = id_
    st.deleted = deleted
    st.fsrs_data = {}
    return st


def test_sqlite_eligible_and_candidate_users_rules() -> None:
    """真实 SQL 验证 _eligible 与 candidate_users：
    - resolved 可用，active 可用
    - suspended / deleted / disabled / 别人 private 不可用
    - 待 AI 判分 pending 不选
    - candidate_users 仅包含有到期题且开启提醒的用户
    """
    engine = _init_sqlite_engine()
    maker = sessionmaker(bind=engine)
    session = maker()

    # 注册一次性监听或由 finally 清理避免跨用例泄漏
    session_counter = 1000

    def _assign_session_id(mapper: Any, connection: Any, target: Any) -> None:
        nonlocal session_counter
        if target.id is None:
            session_counter += 1
            target.id = session_counter

    item_counter = 5000

    def _assign_item_id(mapper: Any, connection: Any, target: Any) -> None:
        nonlocal item_counter
        if target.id is None:
            item_counter += 1
            target.id = item_counter

    event.listen(QbPracticeSession, 'before_insert', _assign_session_id)
    event.listen(QbPracticeSessionItem, 'before_insert', _assign_item_id)
    now = datetime(2026, 11, 2, 20, 0, tzinfo=ZoneInfo('Asia/Shanghai'))

    # 用户1（开启提醒）与用户2（关闭提醒）与用户3（无到期题）
    pref1 = QbUserPracticePreference(user_id=1, review_reminder_enabled=True, review_daily_limit=20, created_by=1)
    pref1.id = 1
    pref2 = QbUserPracticePreference(user_id=2, review_reminder_enabled=False, review_daily_limit=20, created_by=2)
    pref2.id = 2
    pref3 = QbUserPracticePreference(user_id=3, review_reminder_enabled=True, review_daily_limit=20, created_by=3)
    pref3.id = 3
    session.add_all([pref1, pref2, pref3])

    # 题目设置
    # Q1: public active (active state, 到期) -> 可用
    session.add(_make_question(1, 'q1', 'stem1', 'public', 'active'))
    session.add(_make_state(1, 1, 1, 'active', now - timedelta(hours=1)))

    # Q2: public active (resolved state, 到期) -> 可用 (resolved 仍参与回测)
    session.add(_make_question(2, 'q2', 'stem2', 'public', 'active'))
    session.add(_make_state(2, 1, 2, 'resolved', now - timedelta(hours=2)))

    # Q3: public active (suspended state, 到期) -> 不可用
    session.add(_make_question(3, 'q3', 'stem3', 'public', 'active'))
    session.add(_make_state(3, 1, 3, 'suspended', now - timedelta(hours=1)))

    # Q4: public active (active, deleted=1) -> 不可用 (错题已删)
    session.add(_make_question(4, 'q4', 'stem4', 'public', 'active'))
    session.add(_make_state(4, 1, 4, 'active', now - timedelta(hours=1), deleted=1))

    # Q5: disabled question -> 不可用 (题目本身已禁用)
    session.add(_make_question(5, 'q5', 'stem5', 'public', 'disabled'))
    session.add(_make_state(5, 1, 5, 'active', now - timedelta(hours=1)))

    # Q6: deleted question -> 不可用 (题目被逻辑删除)
    session.add(_make_question(6, 'q6', 'stem6', 'public', 'active', deleted=1))
    session.add(_make_state(6, 1, 6, 'active', now - timedelta(hours=1)))

    # Q7: 别人的 private 题 (owner_id=99) -> 不可用
    session.add(_make_question(7, 'q7', 'stem7', 'private', 'active', owner_id=99))
    session.add(_make_state(7, 1, 7, 'active', now - timedelta(hours=1)))

    # Q8: 自己的 private 题 (owner_id=1) -> 可用
    session.add(_make_question(8, 'q8', 'stem8', 'private', 'active', owner_id=1))
    session.add(_make_state(8, 1, 8, 'active', now - timedelta(hours=1)))

    # Q9: 有待 AI 判分 pending 作答 -> 不可用
    session.add(_make_question(9, 'q9', 'stem9', 'public', 'active'))
    session.add(_make_state(9, 1, 9, 'active', now - timedelta(hours=1)))
    att9 = QbQuestionAttempt(
        user_id=1,
        question_id=9,
        attempt_no=1,
        response_data='A',
        grading_status='pending',
        is_correct=None,
    )
    att9.id = 109
    att9.deleted = 0
    session.add(att9)

    # 用户2也有到期题，但未开启提醒；用户3无到期题
    session.add(_make_question(20, 'q20', 'stem20', 'public', 'active'))
    session.add(_make_state(20, 2, 20, 'active', now - timedelta(hours=1), review_count=1))

    # Q10: 负例明确 review_count=0 -> 不可用
    session.add(_make_question(10, 'q10', 'stem10', 'public', 'active'))
    session.add(_make_state(10, 1, 10, 'active', now - timedelta(hours=1), review_count=0))

    session.commit()

    async_db = _SyncSessionAsAsync(session)

    # 1. 验证 candidate_users
    candidates = asyncio.run(qbank_notification_service.candidate_users(async_db, after=0, now=now, limit=10))
    # 只有用户1符合：开启提醒且有到期题；用户2未开启，用户3无题
    assert candidates == [1]

    # 2. 验证 _eligible 过滤规则
    stmt = (
        select(QbWrongQuestionState.question_id)
        .join(QbQuestion, QbQuestion.id == QbWrongQuestionState.question_id)
        .where(*qbank_notification_service._eligible(1, now))
        .order_by(QbWrongQuestionState.question_id)
    )
    eligible_ids = list(session.scalars(stmt).all())
    # 期望包含：1 (active), 2 (resolved), 8 (own private)
    # 排除：3 (suspended), 4 (state deleted), 5 (question disabled),
    # 6 (question deleted), 7 (other private), 9 (pending grading), 10 (review_count=0)
    assert eligible_ids == [1, 2, 8]
    event.remove(QbPracticeSession, 'before_insert', _assign_session_id)
    event.remove(QbPracticeSessionItem, 'before_insert', _assign_item_id)
    session.close()
    engine.dispose()


def test_sqlite_unfinished_session_rules() -> None:
    """真实 SQL 验证 _unfinished：
    - 有效未答卷续接
    - 不续接只有暂停题/已提交题的卷
    """
    engine = _init_sqlite_engine()
    maker = sessionmaker(bind=engine)
    session = maker()

    # 注册一次性监听或由 finally 清理避免跨用例泄漏
    session_counter = 1000

    def _assign_session_id(mapper: Any, connection: Any, target: Any) -> None:
        nonlocal session_counter
        if target.id is None:
            session_counter += 1
            target.id = session_counter

    item_counter = 5000

    def _assign_item_id(mapper: Any, connection: Any, target: Any) -> None:
        nonlocal item_counter
        if target.id is None:
            item_counter += 1
            target.id = item_counter

    event.listen(QbPracticeSession, 'before_insert', _assign_session_id)
    event.listen(QbPracticeSessionItem, 'before_insert', _assign_item_id)
    now = datetime(2026, 11, 2, 20, 0, tzinfo=ZoneInfo('Asia/Shanghai'))

    # Q101, Q102 正常活跃到期
    session.add(_make_question(101, 'q101', 'stem101', 'public', 'active'))
    session.add(_make_question(102, 'q102', 'stem102', 'public', 'active'))
    session.add(_make_state(101, 1, 101, 'active', now - timedelta(hours=1)))
    session.add(_make_state(102, 1, 102, 'active', now - timedelta(hours=1)))

    # 会话1：已提交所有题目 (answered_items == total_items) -> 不被 _unfinished 匹配
    sess1 = QbPracticeSession(
        session_key='sess-1',
        user_id=1,
        status='in_progress',
        total_items=1,
        answered_items=1,
        delivery_config={'recall_message_id': 1001},
    )
    sess1.id = 11
    item1 = QbPracticeSessionItem(session_id=11, question_id=101, position=0)
    item1.id = 201
    resp1 = QbPracticeSessionResponse(session_id=11, session_item_id=201, status='submitted')
    resp1.id = 301
    session.add_all([sess1, item1, resp1])

    # 会话2：未答满，但其中的题 Q103 是 suspended 状态 -> 不续接只有暂停题的卷
    session.add(_make_question(103, 'q103', 'stem103', 'public', 'active'))
    session.add(_make_state(103, 1, 103, 'suspended', now - timedelta(hours=1)))
    sess2 = QbPracticeSession(
        session_key='sess-2',
        user_id=1,
        status='in_progress',
        total_items=1,
        answered_items=0,
        delivery_config={'recall_message_id': 1002},
    )
    sess2.id = 12
    item2 = QbPracticeSessionItem(session_id=12, question_id=103, position=0)
    item2.id = 202
    session.add_all([sess2, item2])

    # 会话3：未答满，且题目 Q101 虽在会话中但已提交 (submitted) -> 不续接只有已提交题的卷
    sess3 = QbPracticeSession(
        session_key='sess-3',
        user_id=1,
        status='in_progress',
        total_items=2,
        answered_items=1,
        delivery_config={'recall_message_id': 1003},
    )
    sess3.id = 13
    item3 = QbPracticeSessionItem(session_id=13, question_id=101, position=0)
    item3.id = 203
    resp3 = QbPracticeSessionResponse(session_id=13, session_item_id=203, status='submitted')
    resp3.id = 303
    # 第二题 Q104 变成 disabled
    session.add(_make_question(104, 'q104', 'stem104', 'public', 'disabled'))
    session.add(_make_state(104, 1, 104, 'active', now - timedelta(hours=1)))
    item3_b = QbPracticeSessionItem(session_id=13, question_id=104, position=1)
    item3_b.id = 204
    session.add_all([sess3, item3, resp3, item3_b])

    # 会话4：有效未答卷！包含 Q102，未答未提交且题目/状态活跃 -> 成功续接！
    sess4 = QbPracticeSession(
        session_key='sess-4',
        user_id=1,
        status='in_progress',
        total_items=1,
        answered_items=0,
        delivery_config={'recall_message_id': 1004},
    )
    sess4.id = 14
    item4 = QbPracticeSessionItem(session_id=14, question_id=102, position=0)
    item4.id = 205
    session.add_all([sess4, item4])

    session.commit()

    async_db = _SyncSessionAsAsync(session)
    with patch('backend.app.question_bank_v2.service.notification_service.timezone.now', return_value=now):
        unfinished = asyncio.run(qbank_notification_service._unfinished(async_db, 1))

    assert unfinished is not None
    assert unfinished.id == 14
    assert unfinished.session_key == 'sess-4'
    event.remove(QbPracticeSession, 'before_insert', _assign_session_id)
    event.remove(QbPracticeSessionItem, 'before_insert', _assign_item_id)
    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_practice_service_create_with_recall_message_id_and_limit() -> None:
    """真实 service 调用 create：
    - 传入 recall_message_id 和保留前缀 session_key 成功
    - 未传 recall_message_id 但使用保留前缀 recall-message- 被拒绝 (RequestError)
    - limit 符合批次大小
    """
    engine = _init_sqlite_engine()
    maker = sessionmaker(bind=engine)
    session = maker()

    # 注册一次性监听或由 finally 清理避免跨用例泄漏
    session_counter = 1000

    def _assign_session_id(mapper: Any, connection: Any, target: Any) -> None:
        nonlocal session_counter
        if target.id is None:
            session_counter += 1
            target.id = session_counter

    item_counter = 5000

    def _assign_item_id(mapper: Any, connection: Any, target: Any) -> None:
        nonlocal item_counter
        if target.id is None:
            item_counter += 1
            target.id = item_counter

    event.listen(QbPracticeSession, 'before_insert', _assign_session_id)
    event.listen(QbPracticeSessionItem, 'before_insert', _assign_item_id)
    # 准备基础题目与答案
    from backend.app.question_bank_v2.model.question import QbQuestionAnswer

    q501 = _make_question(501, 'q501', '题干501', 'public', 'active')
    q502 = _make_question(502, 'q502', '题干502', 'public', 'active')
    session.add_all([q501, q502])
    ans501 = QbQuestionAnswer(question_id=501, answer_data='A', created_by=1)
    ans501.id = 601
    ans502 = QbQuestionAnswer(question_id=502, answer_data='B', created_by=1)
    ans502.id = 602
    session.add_all([ans501, ans502])

    from backend.utils.timezone import timezone

    # 准备对应的错题状态（active/resolved）供 recall_message 校验
    w501 = _make_state(9501, user_id=1, question_id=501, status='active', next_practice_time=timezone.now())
    w502 = _make_state(9502, user_id=1, question_id=502, status='resolved', next_practice_time=timezone.now())
    session.add_all([w501, w502])
    session.commit()

    async_db = _SyncSessionAsAsync(session)

    # 1. 尝试使用保留前缀但未传 recall_message_id -> 拒绝
    with pytest.raises(errors.RequestError, match='该会话标识前缀保留给站内回测消息'):
        await practice_service.create(
            db=async_db,
            user_id=1,
            obj=CreatePracticeSessionParam(
                source_type='custom',
                question_ids=[501, 502],
                session_key='recall-message-777',
                limit=2,
            ),
            recall_message_id=None,
        )

    # 2. 正确传入 recall_message_id 和 limit=2 -> 成功
    detail = await practice_service.create(
        db=async_db,
        user_id=1,
        obj=CreatePracticeSessionParam(
            source_type='custom',
            question_ids=[501, 502],
            session_key='recall-message-777',
            limit=2,
        ),
        recall_message_id=777,
    )

    assert detail.session_key == 'recall-message-777'
    assert detail.total_items == 2
    assert (detail.delivery_config or {}).get('recall_message_id') == 777
    event.remove(QbPracticeSession, 'before_insert', _assign_session_id)
    event.remove(QbPracticeSessionItem, 'before_insert', _assign_item_id)
    session.close()
    engine.dispose()
