from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pydantic import ValidationError
from sqlalchemy import event, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.admin.model.message import Message, MessageStatus, MessageTargetType, MessageType
from backend.app.question_bank_v2.crud.crud_practice import practice_session_dao, practice_session_item_dao
from backend.app.question_bank_v2.model.practice import (
    QbPracticeSession,
    QbPracticeSessionItem,
    QbPracticeSessionResponse,
    QbQuestionAttempt,
)
from backend.app.question_bank_v2.model.question import QbQuestionAnswer
from backend.app.question_bank_v2.model.review import (
    QbWrongQuestionState,
)
from backend.app.question_bank_v2.model.user import QbUserPracticePreference
from backend.app.question_bank_v2.schema.practice import (
    CreatePracticeSessionParam,
    CreateRecallSessionParam,
    SubmitPracticeItemParam,
)
from backend.app.question_bank_v2.service.notification_service import (
    BIZ_SOURCE,
    RECALL_ACTION,
    qbank_notification_service,
)
from backend.app.question_bank_v2.service.practice_service import practice_service
from backend.app.question_bank_v2.tests.test_recall_notifications import (
    _SyncSessionAsAsync,
    _init_sqlite_engine,
    _make_question,
    _make_state,
)
from backend.common.exception import errors
from backend.utils.timezone import timezone


class _RecallSyncSessionAsAsync(_SyncSessionAsAsync):
    """扩展 _SyncSessionAsAsync，支持 message_service.publish 等方法调用的 refresh。"""

    async def refresh(self, instance: Any, attribute_names: Any = None, with_for_update: Any = None) -> None:
        self._session.refresh(instance, attribute_names=attribute_names, with_for_update=with_for_update)


def _bind_sqlite_auto_increment(session: Session) -> dict[str, int]:
    """为 SQLite 内存库自动分配主键，确保真实 CRUD 插入与外键关联完整。"""
    counter = {
        'sess': 1000,
        'item': 5000,
        'msg': 100,
        'resp': 8000,
        'attempt': 9000,
    }

    def allocator(key: str) -> Any:
        def assign(mapper: Any, connection: Any, target: Any) -> None:
            if target.id is None:
                counter[key] += 1
                target.id = counter[key]

        return assign

    for model, key in (
        (QbPracticeSession, 'sess'),
        (QbPracticeSessionItem, 'item'),
        (Message, 'msg'),
        (QbPracticeSessionResponse, 'resp'),
        (QbQuestionAttempt, 'attempt'),
    ):
        event.listen(model, 'before_insert', allocator(key))
    return counter


@pytest.mark.asyncio
async def test_reviewed_due_50_notification_and_open_full_delivery() -> None:
    """需求 1: 50 道 reviewed due 题，用户偏好 review_daily_limit=20，
    真实 notify 发出消息载荷包含全量 50 题（无 batch/next_batch），
    真实 open_practice 一次性创建全部 50 题。
    """
    engine = _init_sqlite_engine()
    maker = sessionmaker(bind=engine)
    session = maker()
    _bind_sqlite_auto_increment(session)

    now = datetime(2026, 11, 2, 21, 0, tzinfo=ZoneInfo('Asia/Shanghai'))
    user_id = 1

    pref = QbUserPracticePreference(
        user_id=user_id,
        review_reminder_enabled=True,
        review_reminder_timezone='Asia/Shanghai',
        review_reminder_time=time(20, 0),
        review_daily_limit=20,  # 偏好设为20
        created_by=user_id,
    )
    pref.id = 1
    session.add(pref)

    q_ids = list(range(1, 51))
    for qid in q_ids:
        q = _make_question(qid, f'code_{qid}', f'stem_{qid}', visibility='public', status='active')
        ans = QbQuestionAnswer(question_id=qid, answer_data='A', created_by=user_id)
        ans.id = qid
        st = _make_state(qid, user_id, qid, status='active', next_practice_time=now - timedelta(minutes=10))
        st.review_count = 1  # 已复盘
        session.add_all([q, ans, st])

    session.commit()
    async_db = _RecallSyncSessionAsAsync(session)

    # 1. 真实通知发送（穿透真实 due_queue）
    sent = await qbank_notification_service.notify_practice_due(db=async_db, user_id=user_id, now=now)
    assert sent is True

    # 验证消息记录
    msg: Message | None = session.scalar(
        select(Message).where(Message.biz_source == BIZ_SOURCE, Message.user_id == user_id)
    )
    assert msg is not None
    payload = msg.payload or {}
    assert payload['action'] == RECALL_ACTION
    assert len(payload['question_ids']) == 50
    assert payload['question_ids'] == q_ids
    assert payload['due_count'] == 50
    assert 'batch_size' not in payload  # 不限题，无分批
    assert 'next_batch' not in payload

    # 2. 真实 open_practice 打开会话
    detail = await qbank_notification_service.open_practice(db=async_db, user_id=user_id, message_id=msg.id)
    assert detail.total_items == 50
    assert len(detail.items) == 50
    assert sorted(item.question_id for item in detail.items) == q_ids

    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_schema_and_real_create_501_questions() -> None:
    """需求 2: 501 题校验：
    - 公开 CreatePracticeSessionParam 严格拒绝 501 题 (>500 limit/max_length)
    - 内部 CreateRecallSessionParam 允许 501 题
    - 真实 practice_service.create 成功创建 501 题全量会话
    """
    q_ids = list(range(1, 502))
    assert len(q_ids) == 501

    # 1. 公开 Schema 拦截
    with pytest.raises(ValidationError) as exc_info:
        CreatePracticeSessionParam(
            source_type='custom',
            question_ids=q_ids,
            limit=501,
        )
    err_fields = [e['loc'][0] for e in exc_info.value.errors()]
    assert 'question_ids' in err_fields or 'limit' in err_fields

    # 2. 内部 Schema 放行
    recall_param = CreateRecallSessionParam(
        source_type='custom',
        question_ids=q_ids,
        limit=501,
        session_key='recall-message-9999',
    )
    assert len(recall_param.question_ids) == 501
    assert recall_param.limit == 501

    # 3. 真实 SQLite 数据库中创建 501 道题并由 practice_service.create 全量落库
    engine = _init_sqlite_engine()
    maker = sessionmaker(bind=engine)
    session = maker()
    _bind_sqlite_auto_increment(session)

    user_id = 1
    now = timezone.now()

    for qid in q_ids:
        q = _make_question(qid, f'code_{qid}', f'stem_{qid}', visibility='public', status='active')
        ans = QbQuestionAnswer(question_id=qid, answer_data='A', created_by=user_id)
        ans.id = qid
        st = _make_state(qid, user_id, qid, status='active', next_practice_time=now - timedelta(hours=1))
        st.review_count = 1
        session.add_all([q, ans, st])

    session.commit()
    async_db = _RecallSyncSessionAsAsync(session)

    detail = await practice_service.create(
        db=async_db,
        user_id=user_id,
        obj=recall_param,
        recall_message_id=9999,
    )
    assert detail.total_items == 501
    assert len(detail.items) == 501
    assert detail.session_key == 'recall-message-9999'

    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_due_queue_excludes_unreviewed_suspended_deleted_pending_private() -> None:
    """需求 3: 严格测试 due_queue 过滤规则：
    - 未复盘题 (review_count == 0) 排除
    - 暂停错题 (suspended) 排除
    - 删除错题 (deleted == 1) 排除
    - 题目本身禁用/删除 (disabled / deleted == 1) 排除
    - 待 AI 判分 (attempt grading_status == 'pending') 排除
    - 别人私有题 (private and owner_id != user_id) 排除
    - 合格题（active/resolved 且 review_count > 0 且到期）纳入
    """
    engine = _init_sqlite_engine()
    maker = sessionmaker(bind=engine)
    session = maker()
    _bind_sqlite_auto_increment(session)

    now = datetime(2026, 11, 2, 20, 0, tzinfo=ZoneInfo('Asia/Shanghai'))
    user_id = 1

    # Q1: 正常活跃且已复盘 (review_count=1) -> 纳入
    session.add(_make_question(1, 'q1', 'stem1', 'public', 'active'))
    st1 = _make_state(1, user_id, 1, 'active', now - timedelta(hours=1))
    st1.review_count = 1
    session.add(st1)

    # Q2: 正常 resolved 且已复盘 (review_count=2) -> 纳入
    session.add(_make_question(2, 'q2', 'stem2', 'public', 'active'))
    st2 = _make_state(2, user_id, 2, 'resolved', now - timedelta(hours=1))
    st2.review_count = 2
    session.add(st2)

    # Q3: 自己的私有题 (owner_id=user_id) 且已复盘 -> 纳入
    session.add(_make_question(3, 'q3', 'stem3', 'private', 'active', owner_id=user_id))
    st3 = _make_state(3, user_id, 3, 'active', now - timedelta(hours=1))
    st3.review_count = 1
    session.add(st3)

    # Q4: 未复盘题 (review_count=0) -> 排除
    session.add(_make_question(4, 'q4', 'stem4', 'public', 'active'))
    st4 = _make_state(4, user_id, 4, 'active', now - timedelta(hours=1))
    st4.review_count = 0
    session.add(st4)

    # Q5: 暂停题 (status='suspended') -> 排除
    session.add(_make_question(5, 'q5', 'stem5', 'public', 'active'))
    st5 = _make_state(5, user_id, 5, 'suspended', now - timedelta(hours=1))
    st5.review_count = 1
    session.add(st5)

    # Q6: 错题状态已删除 (deleted=1) -> 排除
    session.add(_make_question(6, 'q6', 'stem6', 'public', 'active'))
    st6 = _make_state(6, user_id, 6, 'active', now - timedelta(hours=1), deleted=1)
    st6.review_count = 1
    session.add(st6)

    # Q7: 题目本身禁用 (disabled) -> 排除
    session.add(_make_question(7, 'q7', 'stem7', 'public', 'disabled'))
    st7 = _make_state(7, user_id, 7, 'active', now - timedelta(hours=1))
    st7.review_count = 1
    session.add(st7)

    # Q8: 题目本身删除 (deleted=1) -> 排除
    session.add(_make_question(8, 'q8', 'stem8', 'public', 'active', deleted=1))
    st8 = _make_state(8, user_id, 8, 'active', now - timedelta(hours=1))
    st8.review_count = 1
    session.add(st8)

    # Q9: 别人的私有题 (owner_id=999) -> 排除
    session.add(_make_question(9, 'q9', 'stem9', 'private', 'active', owner_id=999))
    st9 = _make_state(9, user_id, 9, 'active', now - timedelta(hours=1))
    st9.review_count = 1
    session.add(st9)

    # Q10: 待 AI 判分 pending -> 排除
    session.add(_make_question(10, 'q10', 'stem10', 'public', 'active'))
    st10 = _make_state(10, user_id, 10, 'active', now - timedelta(hours=1))
    st10.review_count = 1
    session.add(st10)
    att10 = QbQuestionAttempt(
        user_id=user_id,
        question_id=10,
        attempt_no=1,
        response_data='ans',
        grading_status='pending',
        is_correct=None,
    )
    att10.id = 110
    att10.deleted = 0
    session.add(att10)

    # Q11: 尚未到期 (next_practice_time > cutoff) -> 排除
    session.add(_make_question(11, 'q11', 'stem11', 'public', 'active'))
    st11 = _make_state(11, user_id, 11, 'active', now + timedelta(hours=1))
    st11.review_count = 1
    session.add(st11)

    session.commit()
    async_db = _RecallSyncSessionAsAsync(session)

    # 验证真实 due_queue
    due_stmt = qbank_notification_service.due_queue(user_id, now).order_by(QbWrongQuestionState.question_id)
    due_ids = list((await async_db.scalars(due_stmt)).all())
    assert due_ids == [1, 2, 3]

    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_resume_appends_all_reviewed_due_preserves_position_and_attempt() -> None:
    """需求 4: _resume 旧限量未答卷：
    - 原卷已有 Q1(作答已提交) 与 Q2(未答)
    - 队列中有新到期且已复盘题 Q3, Q4，以及未复盘题 Q5
    - _resume 会追加所有已复盘到期题 (Q3, Q4)，不追加未复盘题 Q5
    - 保持原有 item positions (0, 1) 以及已作答 response / attempt 事实完全不变
    - 新追加 item 的 position 顺延为 2, 3
    """
    engine = _init_sqlite_engine()
    maker = sessionmaker(bind=engine)
    session = maker()
    _bind_sqlite_auto_increment(session)

    user_id = 1
    now = timezone.now()

    # 准备题目 Q1~Q5
    for qid in range(1, 6):
        session.add(_make_question(qid, f'q{qid}', f'stem{qid}', 'public', 'active'))
        ans = QbQuestionAnswer(question_id=qid, answer_data='A', created_by=user_id)
        ans.id = qid
        session.add(ans)

    # Q1, Q2, Q3, Q4 已复盘；Q5 未复盘
    for qid in range(1, 5):
        st = _make_state(qid, user_id, qid, 'active', now - timedelta(hours=1))
        st.review_count = 1
        st.entry_metadata = {'section_name': '常识判断' if qid % 2 else '言语理解'}
        session.add(st)
    st5 = _make_state(5, user_id, 5, 'active', now - timedelta(hours=1))
    st5.review_count = 0  # 未复盘
    session.add(st5)

    # 旧限量未答卷 (只含 Q1, Q2)
    old_sess = QbPracticeSession(
        session_key='recall-message-100',
        user_id=user_id,
        status='in_progress',
        total_items=2,
        answered_items=1,
        delivery_config={'recall_message_id': 100, 'recall_due_before': now.isoformat()},
    )
    session.add(old_sess)
    session.flush()

    item1 = QbPracticeSessionItem(session_id=old_sess.id, question_id=1, position=0)
    item2 = QbPracticeSessionItem(session_id=old_sess.id, question_id=2, position=1)
    session.add_all([item1, item2])
    session.flush()

    # Q1 有已提交的 response 和 attempt
    resp1 = QbPracticeSessionResponse(
        session_id=old_sess.id,
        session_item_id=item1.id,
        response_data='A',
        status='submitted',
        is_correct=True,
    )
    att1 = QbQuestionAttempt(
        user_id=user_id,
        question_id=1,
        session_id=old_sess.id,
        session_item_id=item1.id,
        attempt_no=1,
        response_data='A',
        is_correct=True,
        grading_status='graded',
        submitted_time=now - timedelta(minutes=10),
    )
    session.add_all([resp1, att1])

    # 准备新消息
    msg = Message(
        title='回测提醒',
        content='内容',
        target_type=MessageTargetType.USER,
        user_id=user_id,
        message_type=MessageType.PERSONAL,
        status=MessageStatus.ENABLED,
        publish_time=now,
        biz_source=BIZ_SOURCE,
        biz_id='practice_due:1:resume',
        payload={
            'action': RECALL_ACTION,
            'question_ids': [1, 2, 3, 4],
            'due_before': now.isoformat(),
            'session_key': old_sess.session_key,
            'due_count': 4,
        },
    )
    session.add(msg)
    session.commit()

    async_db = _SyncSessionAsAsync(session)

    # 执行 open_practice 触发 _resume
    detail = await qbank_notification_service.open_practice(db=async_db, user_id=user_id, message_id=msg.id)

    # 验证总题数扩展为 4 题 (Q1, Q2, Q3, Q4，排除了 Q5)
    assert detail.total_items == 4
    assert detail.session_key == 'recall-message-100'
    assert [item.question_id for item in detail.items] == [1, 3, 2, 4]
    assert [item.position for item in detail.items] == [0, 1, 2, 3]
    assert [item.section_name for item in detail.items] == ['常识判断', '常识判断', '言语理解', '言语理解']

    # 查阅数据库中真实 items
    db_items = await practice_session_item_dao.get_all(async_db, old_sess.id)
    assert len(db_items) == 4
    item_map = {it['question_id']: it for it in db_items}

    # 验证原 Q1 位置为 0，作答状态仍为 submitted，答案未被篡改
    assert item_map[1]['position'] == 0
    assert item_map[1]['response_status'] == 'submitted'
    assert item_map[1]['is_correct'] is True

    # 验证原 Q2 位置为 1
    assert item_map[2]['position'] == 1

    # 验证新追加题目 Q3, Q4 的 position 顺延为 2, 3
    assert item_map[3]['position'] == 2
    assert item_map[4]['position'] == 3
    assert 5 not in item_map  # 未复盘题未被追加

    # 验证 Q1 的 attempt 记录完好无损
    att = session.scalar(select(QbQuestionAttempt).where(QbQuestionAttempt.session_item_id == item1.id))
    assert att is not None
    assert att.attempt_no == 1
    assert att.response_data == 'A'

    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_repeated_open_no_duplicate_append() -> None:
    """需求 5: 重复 open 同一回测消息，幂等续接，不会重复追加题目。"""
    engine = _init_sqlite_engine()
    maker = sessionmaker(bind=engine)
    session = maker()
    _bind_sqlite_auto_increment(session)

    user_id = 1
    now = timezone.now()

    for qid in [101, 102]:
        session.add(_make_question(qid, f'q{qid}', f'stem{qid}', 'public', 'active'))
        ans = QbQuestionAnswer(question_id=qid, answer_data='A', created_by=user_id)
        ans.id = qid
        session.add(ans)
        st = _make_state(qid, user_id, qid, 'active', now - timedelta(hours=1))
        st.review_count = 1
        session.add(st)

    msg = Message(
        title='回测提醒',
        content='内容',
        target_type=MessageTargetType.USER,
        user_id=user_id,
        message_type=MessageType.PERSONAL,
        status=MessageStatus.ENABLED,
        publish_time=now,
        biz_source=BIZ_SOURCE,
        biz_id='practice_due:1:dedup',
        payload={
            'action': RECALL_ACTION,
            'question_ids': [101, 102],
            'due_before': now.isoformat(),
            'session_key': None,
            'due_count': 2,
        },
    )
    session.add(msg)
    session.commit()

    async_db = _SyncSessionAsAsync(session)

    # 首次 open 创建卷
    res1 = await qbank_notification_service.open_practice(db=async_db, user_id=user_id, message_id=msg.id)
    assert res1.total_items == 2
    assert len(res1.items) == 2

    # 二次 open 重复点击
    res2 = await qbank_notification_service.open_practice(db=async_db, user_id=user_id, message_id=msg.id)
    assert res2.session_key == res1.session_key
    assert res2.total_items == 2
    assert len(res2.items) == 2

    # 三次 open
    res3 = await qbank_notification_service.open_practice(db=async_db, user_id=user_id, message_id=msg.id)
    assert res3.total_items == 2

    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_closed_session_with_remaining_creates_independent_resume_session() -> None:
    """需求 6: 旧 closed 回测卷（例如已 submitted），若消息截止时仍有剩余到期已复盘题：
    - 创建独立完整的新会话 (recall-message-{id}-resume-{previous_id})
    - 绝不修改旧 closed 会话的作答和题目
    """
    engine = _init_sqlite_engine()
    maker = sessionmaker(bind=engine)
    session = maker()
    _bind_sqlite_auto_increment(session)

    user_id = 1
    now = timezone.now()

    # Q1, Q2 均活跃且已复盘
    for qid in [1, 2]:
        session.add(_make_question(qid, f'q{qid}', f'stem{qid}', 'public', 'active'))
        ans = QbQuestionAnswer(question_id=qid, answer_data='A', created_by=user_id)
        ans.id = qid
        session.add(ans)

    # Q1 已完成并在旧卷中提交；Q2 仍到期且已复盘
    st1 = _make_state(1, user_id, 1, 'active', now - timedelta(hours=2))
    st1.review_count = 1
    # Q1 在旧卷作答后，last_practice_time 在 cutoff 之前
    st1.last_practice_time = now - timedelta(hours=2)

    st2 = _make_state(2, user_id, 2, 'active', now - timedelta(hours=1))
    st2.review_count = 1
    session.add_all([st1, st2])

    # 已交卷的旧会话 (status='submitted')
    old_sess = QbPracticeSession(
        session_key='old-closed-sess',
        user_id=user_id,
        status='submitted',
        total_items=1,
        answered_items=1,
        delivery_config={'recall_message_id': 555, 'recall_due_before': now.isoformat()},
    )
    session.add(old_sess)
    session.flush()

    it1 = QbPracticeSessionItem(session_id=old_sess.id, question_id=1, position=0)
    session.add(it1)
    session.flush()

    resp1 = QbPracticeSessionResponse(
        session_id=old_sess.id,
        session_item_id=it1.id,
        response_data='A',
        status='submitted',
        is_correct=True,
    )
    session.add(resp1)

    msg = Message(
        title='回测提醒',
        content='内容',
        target_type=MessageTargetType.USER,
        user_id=user_id,
        message_type=MessageType.PERSONAL,
        status=MessageStatus.ENABLED,
        publish_time=now,
        biz_source=BIZ_SOURCE,
        biz_id='practice_due:1:closed_resume',
        payload={
            'action': RECALL_ACTION,
            'question_ids': [1, 2],
            'due_before': now.isoformat(),
            'session_key': old_sess.session_key,
            'due_count': 2,
        },
    )
    session.add(msg)
    session.commit()

    async_db = _SyncSessionAsAsync(session)

    # 打开消息：因为 old_sess 已 submitted，系统检测剩余到期题并创建独立 resume 会话
    res = await qbank_notification_service.open_practice(db=async_db, user_id=user_id, message_id=msg.id)

    # 验证新会话独立生成
    expected_prefix = f'recall-message-{msg.id}-resume-{old_sess.id}'
    assert res.session_key == expected_prefix
    assert res.status == 'in_progress'

    # 验证旧会话的记录毫发无损，状态仍为 submitted，题目数仍为 1
    old_db_sess = await practice_session_dao.get_by_key(async_db, 'old-closed-sess', user_id=user_id)
    assert old_db_sess is not None
    assert old_db_sess.status == 'submitted'
    assert old_db_sess.total_items == 1
    assert old_db_sess.answered_items == 1

    old_items = await practice_session_item_dao.get_all(async_db, old_sess.id)
    assert len(old_items) == 1
    assert old_items[0]['question_id'] == 1

    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_closed_session_with_no_remaining_safe_view_no_remake() -> None:
    """需求 7: 无剩余题时的 closed 回测卷：
    - 旧卷已提交且所有题目在之后均不再处于到期队列
    - open_practice 安全返回原已提交会话的查看视图，不强行报错也不重复建卷或重做
    """
    engine = _init_sqlite_engine()
    maker = sessionmaker(bind=engine)
    session = maker()
    _bind_sqlite_auto_increment(session)

    user_id = 1
    now = timezone.now()

    q1 = _make_question(1, 'q1', 'stem1', 'public', 'active')
    ans1 = QbQuestionAnswer(question_id=1, answer_data='A', created_by=user_id)
    ans1.id = 1
    # 下次练习时间在遥远未来，不再到期
    st1 = _make_state(1, user_id, 1, 'active', now + timedelta(days=7))
    st1.review_count = 1
    session.add_all([q1, ans1, st1])

    old_sess = QbPracticeSession(
        session_key='old-finished-sess',
        user_id=user_id,
        status='submitted',
        total_items=1,
        answered_items=1,
        delivery_config={'recall_message_id': 666, 'recall_due_before': now.isoformat()},
    )
    session.add(old_sess)
    session.flush()

    it1 = QbPracticeSessionItem(session_id=old_sess.id, question_id=1, position=0)
    session.add(it1)
    session.flush()

    resp1 = QbPracticeSessionResponse(
        session_id=old_sess.id,
        session_item_id=it1.id,
        response_data='A',
        status='submitted',
        is_correct=True,
    )
    session.add(resp1)

    msg = Message(
        title='回测提醒',
        content='内容',
        target_type=MessageTargetType.USER,
        user_id=user_id,
        message_type=MessageType.PERSONAL,
        status=MessageStatus.ENABLED,
        publish_time=now,
        biz_source=BIZ_SOURCE,
        biz_id='practice_due:1:finished_safe_view',
        payload={
            'action': RECALL_ACTION,
            'question_ids': [1],
            'due_before': now.isoformat(),
            'session_key': old_sess.session_key,
            'due_count': 1,
        },
    )
    session.add(msg)
    session.commit()

    async_db = _SyncSessionAsAsync(session)

    # 打开消息：安全回看旧卷
    res = await qbank_notification_service.open_practice(db=async_db, user_id=user_id, message_id=msg.id)
    assert res.session_key == 'old-finished-sess'
    assert res.status == 'submitted'
    assert res.total_items == 1
    assert len(res.items) == 1
    assert res.items[0].question_id == 1

    session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_unreviewed_question_get_filtered_and_submit_guard_rejected() -> None:
    """需求 8: 旧未复盘题：
    - get 视图过滤：旧会话中若存在 review_count == 0 的题目，在 practice_service.get 中被动态过滤
    - submit guard 防御：直接调用 submit_item 提交该未复盘题时，被 _get_submittable_question 拒绝抛出 ConflictError
    """
    engine = _init_sqlite_engine()
    maker = sessionmaker(bind=engine)
    session = maker()
    _bind_sqlite_auto_increment(session)

    user_id = 1
    now = timezone.now()

    # Q1: 活跃但未复盘 (review_count = 0)
    q1 = _make_question(1, 'q1', 'stem1', 'public', 'active')
    ans1 = QbQuestionAnswer(question_id=1, answer_data='A', created_by=user_id)
    ans1.id = 1
    st1 = _make_state(1, user_id, 1, 'active', now - timedelta(hours=1))
    st1.review_count = 0  # 重点：review_count == 0 未复盘
    session.add_all([q1, ans1, st1])

    # 模拟历史遗留回测会话包含了 Q1
    sess = QbPracticeSession(
        session_key='recall-message-legacy',
        user_id=user_id,
        status='in_progress',
        total_items=1,
        answered_items=0,
        delivery_config={'recall_message_id': 777, 'recall_due_before': now.isoformat()},
    )
    session.add(sess)
    session.flush()

    item1 = QbPracticeSessionItem(session_id=sess.id, question_id=1, position=0)
    session.add(item1)
    session.commit()

    async_db = _SyncSessionAsAsync(session)

    # 1. 验证 get 视图过滤：未复盘题被过滤，total_items 与 items 为空
    detail = await practice_service.get(db=async_db, session_key='recall-message-legacy', user_id=user_id)
    assert detail.total_items == 0
    assert len(detail.items) == 0

    # 2. 验证 submit guard 拦截：提交未复盘题目直接抛出 ConflictError
    with pytest.raises(errors.ConflictError, match='本题尚未复盘，不属于复盘回测，请刷新练习'):
        await practice_service.submit_item(
            db=async_db,
            session_key='recall-message-legacy',
            user_id=user_id,
            session_item_id=item1.id,
            obj=SubmitPracticeItemParam(
                response_data='A',
                duration_ms=1500,
                submission_key='sub-unreviewed-guard-1',
            ),
        )

    session.close()
    engine.dispose()
