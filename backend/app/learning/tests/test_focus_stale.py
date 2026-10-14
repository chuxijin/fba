"""学习专注过期收口：一次忘记结束的专注不能把规划页永久锁死。

线上问题：番茄模块留下一条 paused 记录（ended_at 为空），规划页每次进入都把它
当成「当前专注」，于是右侧「添加」按钮消失、点日期/任务只提示「请先结束当前专注」。
"""

import asyncio

from datetime import datetime, timedelta
from typing import Any

import pytest

from backend.app.learning.enums import LearningFocusMode, LearningFocusStatus
from backend.app.learning.model.execution import LearningFocusSession
from backend.app.learning.schema.execution import StartLearningFocusParam
from backend.app.learning.service import execution_service as execution_service_module
from backend.app.learning.service.execution_service import (
    FOCUS_SESSION_STALE_HOURS,
    LearningExecutionService,
    learning_execution_service,
)
from backend.common.exception import errors
from backend.utils.timezone import timezone

USER_ID = 20
SESSION_ID = 8


def make_session(*, age_hours: float, status: str = LearningFocusStatus.paused.value) -> LearningFocusSession:
    session = LearningFocusSession(
        task_id=None,
        user_id=USER_ID,
        planned_minutes=25,
        mode=LearningFocusMode.pomodoro.value,
    )
    # 未 flush 的 ORM 实例取不到列默认值，这里按「数据库里那一行」补齐
    session.id = SESSION_ID
    session.status = status
    session.started_at = timezone.now() - timedelta(hours=age_hours)
    session.focused_seconds = 0
    session.paused_seconds = 95
    session.interrupt_count = 0
    session.paused_at = timezone.now() - timedelta(hours=max(age_hours - 0.1, 0))
    session.ended_at = None
    session.remark = None
    return session


class FakeFocusDao:
    """内存版 DAO：expire_stale 收口之后，那条记录不再算「当前专注」。"""

    def __init__(self, *, current: LearningFocusSession | None = None) -> None:
        self.current = current
        self.expired: list[int] = []
        self.expire_calls: list[tuple[int, datetime]] = []

    async def get_current(self, db: Any, user_id: int) -> LearningFocusSession | None:
        return self.current

    async def expire_stale(self, db: Any, user_id: int, *, before: datetime) -> int:
        self.expire_calls.append((user_id, before))
        if self.current is None or self.current.started_at > before:
            return 0
        self.expired.append(int(self.current.id))
        self.current = None
        return 1


class FakeDB:
    """够用的假会话：只承担 add/flush/refresh。"""

    def __init__(self, *, next_id: int = 101) -> None:
        self.added: list[LearningFocusSession] = []
        self.next_id = next_id
        self.flush_count = 0

    def add(self, obj: LearningFocusSession) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flush_count += 1

    async def refresh(self, obj: LearningFocusSession) -> None:
        obj.id = self.next_id
        obj.status = LearningFocusStatus.running.value
        obj.started_at = timezone.now()
        obj.focused_seconds = 0
        obj.paused_seconds = 0
        obj.interrupt_count = 0
        obj.paused_at = None
        obj.ended_at = None
        obj.remark = None


@pytest.fixture
def dao(monkeypatch: pytest.MonkeyPatch) -> FakeFocusDao:
    fake = FakeFocusDao()
    monkeypatch.setattr(execution_service_module, 'learning_focus_dao', fake)
    return fake


def test_expired_session_is_not_current_focus(dao: FakeFocusDao) -> None:
    """13 小时前开始的 paused 记录不再作为当前专注返回。"""
    dao.current = make_session(age_hours=FOCUS_SESSION_STALE_HOURS + 1)

    detail = asyncio.run(learning_execution_service.get_current_focus(db=FakeDB(), user_id=USER_ID))

    assert detail is None


def test_fresh_session_is_still_returned(dao: FakeFocusDao) -> None:
    """刚暂停的专注仍然正常返回，不受收口影响。"""
    dao.current = make_session(age_hours=0.2)

    detail = asyncio.run(learning_execution_service.get_current_focus(db=FakeDB(), user_id=USER_ID))

    assert detail is not None
    assert detail.id == SESSION_ID
    assert detail.status == LearningFocusStatus.paused


def test_start_focus_expires_forgotten_session_instead_of_conflicting(dao: FakeFocusDao) -> None:
    """存在过期专注时可以开新的，并且旧的被收口。"""
    dao.current = make_session(age_hours=FOCUS_SESSION_STALE_HOURS + 1)
    db = FakeDB()

    detail = asyncio.run(
        learning_execution_service.start_focus(
            db=db,
            task_id=None,
            user_id=USER_ID,
            obj=StartLearningFocusParam(planned_minutes=25, mode=LearningFocusMode.pomodoro),
        )
    )

    assert dao.expired == [SESSION_ID]
    assert detail.id == db.next_id
    assert len(db.added) == 1
    # 收口阈值 = 现在 - 12 小时
    user_id, before = dao.expire_calls[0]
    assert user_id == USER_ID
    delta = timezone.now() - before
    assert timedelta(hours=FOCUS_SESSION_STALE_HOURS - 1) < delta < timedelta(hours=FOCUS_SESSION_STALE_HOURS + 1)


def test_start_focus_still_conflicts_with_running_session(dao: FakeFocusDao) -> None:
    """真正在进行的专注依旧拦住新专注，不能变成可以并发开两个。"""
    dao.current = make_session(age_hours=0.1, status=LearningFocusStatus.running.value)
    db = FakeDB()

    with pytest.raises(errors.ConflictError) as exc:
        asyncio.run(
            learning_execution_service.start_focus(
                db=db,
                task_id=None,
                user_id=USER_ID,
                obj=StartLearningFocusParam(planned_minutes=25, mode=LearningFocusMode.pomodoro),
            )
        )

    assert '请先结束当前专注' in str(exc.value.msg)
    assert db.added == []


def test_stale_boundary() -> None:
    """边界：达到阈值算过期，未达到不算。"""
    at_threshold = make_session(age_hours=FOCUS_SESSION_STALE_HOURS)
    just_before = make_session(age_hours=FOCUS_SESSION_STALE_HOURS - 0.01)
    # 用记录自己的开始时间推边界，避免断言落在阈值前后几个微秒上
    boundary = at_threshold.started_at + timedelta(hours=FOCUS_SESSION_STALE_HOURS)

    assert LearningExecutionService._is_stale(at_threshold, boundary) is True
    assert LearningExecutionService._is_stale(just_before, boundary) is False
