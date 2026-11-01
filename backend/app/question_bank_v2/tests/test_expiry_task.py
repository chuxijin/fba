"""V2 练习到期兜底定时任务回归：单场失败隔离、幂等计数与 beat 注册。

全部依赖使用内存 fake：不启动 Celery worker/beat，也不连接真实数据库或 Redis。
"""

from __future__ import annotations

import importlib.util
import sys
import types

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

if TYPE_CHECKING:
    from types import TracebackType

_APP_PATH = Path(__file__).resolve().parents[2]
_TASKS_PATH = _APP_PATH / 'task' / 'tasks' / 'qbank_v2' / 'tasks.py'
_BEAT_PATH = _APP_PATH / 'task' / 'tasks' / 'beat.py'

_EXPECTED_TASK_NAME = 'qbank_v2:expire_practice_sessions'


class _FakeCeleryApp:
    """celery_app 替身：只记录 task 装饰器注册的任务名，不触达 broker/backend。"""

    def __init__(self) -> None:
        self.task_names: list[str] = []

    def task(self, *args: Any, **kwargs: Any) -> Any:
        task_name = kwargs.get('name')

        def decorator(func: Any) -> Any:
            self.task_names.append(task_name)
            return func

        return decorator


class _FakeCrontab:
    """TzAwareCrontab 替身：只保留构造参数，避免引入真实调度对象。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs


def _install_fake_task_deps(monkeypatch: pytest.MonkeyPatch) -> _FakeCeleryApp:
    """在导入任务模块前注入 celery 与 crontab 替身，阻断真实 Celery 初始化。"""
    fake_celery = types.ModuleType('backend.app.task.celery')
    fake_app = _FakeCeleryApp()
    fake_celery.celery_app = fake_app
    monkeypatch.setitem(sys.modules, 'backend.app.task.celery', fake_celery)

    fake_crontab = types.ModuleType('backend.app.task.utils.tzcrontab')
    fake_crontab.TzAwareCrontab = _FakeCrontab
    monkeypatch.setitem(sys.modules, 'backend.app.task.utils.tzcrontab', fake_crontab)
    return fake_app


def _load_module(path: Path, name: str) -> types.ModuleType:
    """按文件路径独立加载模块，避免复用已绑定真实 celery_app 的缓存模块。"""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeQueryResult:
    def __init__(self, rows: list[tuple[str, int]]) -> None:
        self._rows = list(rows)

    def all(self) -> list[tuple[str, int]]:
        return list(self._rows)


class _DiscoveryDB:
    """到期会话发现查询的最小 db：只实现 execute().all()。"""

    def __init__(self, owner: _FakeAsyncDB) -> None:
        self.owner = owner

    async def execute(self, statement: Any) -> _FakeQueryResult:
        self.owner.events.append('query')
        self.owner.queries.append(statement)
        return _FakeQueryResult(self.owner.pending_rows)


class _DiscoveryContext:
    def __init__(self, owner: _FakeAsyncDB) -> None:
        self.owner = owner

    async def __aenter__(self) -> _DiscoveryDB:
        return _DiscoveryDB(self.owner)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False


class _TransactionContext:
    """async_db_session.begin() 替身：正常退出记 commit，异常退出记 rollback。"""

    def __init__(self, owner: _FakeAsyncDB) -> None:
        self.owner = owner

    async def __aenter__(self) -> SimpleNamespace:
        self.owner.events.append('begin')
        return SimpleNamespace()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        self.owner.events.append('rollback' if exc_type is not None else 'commit')
        return False


class _FakeAsyncDB:
    """async_db_session 替身：可调用（发现查询）且提供 begin()。"""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.queries: list[Any] = []
        self.pending_rows: list[tuple[str, int]] = []
        self.begin_calls = 0

    def __call__(self) -> _DiscoveryContext:
        return _DiscoveryContext(self)

    def begin(self) -> _TransactionContext:
        self.begin_calls += 1
        return _TransactionContext(self)


class _FakeSessionDAO:
    """practice_session_dao 替身：记录取会话时的 user_id 与 for_update。"""

    def __init__(self, sessions: dict[str, Any]) -> None:
        self.sessions = sessions
        self.calls: list[dict[str, Any]] = []

    async def get_by_key(
        self,
        db: Any,
        session_key: str,
        *,
        user_id: int | None = None,
        for_update: bool = False,
    ) -> Any:
        self.calls.append({'session_key': session_key, 'user_id': user_id, 'for_update': for_update})
        return self.sessions.get(session_key)


def _make_expire(outcomes: dict[str, Any]) -> AsyncMock:
    """按 session_key 返回成功/失败，异常用于模拟单场结算崩溃。"""

    def side_effect(*, db: Any, session: Any) -> bool:
        outcome = outcomes[session.session_key]
        if isinstance(outcome, Exception):
            raise outcome
        return bool(outcome)

    return AsyncMock(side_effect=side_effect)


def _ignore_exception(*args: Any, **kwargs: Any) -> None:
    """吞掉失败场次的日志输出，保持测试输出干净。"""


def _prepare(monkeypatch: pytest.MonkeyPatch, sessions: dict[str, Any], outcomes: dict[str, Any]) -> Any:
    """加载任务模块并替换全部外部依赖。"""
    fake_app = _install_fake_task_deps(monkeypatch)
    tasks = _load_module(_TASKS_PATH, '_test_qbank_v2_expiry_task_under_test')
    monkeypatch.setattr(tasks, 'log', SimpleNamespace(exception=_ignore_exception))

    fake_db = _FakeAsyncDB()
    dao = _FakeSessionDAO(sessions)
    monkeypatch.setattr(tasks, 'async_db_session', fake_db)
    monkeypatch.setattr(tasks.practice_session_dao, 'get_by_key', dao.get_by_key)
    monkeypatch.setattr(tasks.practice_service, '_expire_if_due', _make_expire(outcomes))
    return SimpleNamespace(module=tasks, fake_app=fake_app, fake_db=fake_db, dao=dao)


async def test_failed_session_rolls_back_and_next_session_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    """第一场抛异常应回滚且不计入 settled，第二场成功提交并计入 settled。"""
    ctx = _prepare(
        monkeypatch,
        {
            'sk-fail': SimpleNamespace(session_key='sk-fail'),
            'sk-ok': SimpleNamespace(session_key='sk-ok'),
        },
        {'sk-fail': RuntimeError('settle boom'), 'sk-ok': True},
    )
    ctx.fake_db.pending_rows = [('sk-fail', 11), ('sk-ok', 22)]

    result = await ctx.module.expire_practice_sessions()

    assert result == {'settled': 1, 'failed': 1}
    assert ctx.fake_app.task_names == [_EXPECTED_TASK_NAME]
    assert ctx.fake_db.events == ['query', 'begin', 'rollback', 'begin', 'commit']
    assert ctx.dao.calls == [
        {'session_key': 'sk-fail', 'user_id': 11, 'for_update': True},
        {'session_key': 'sk-ok', 'user_id': 22, 'for_update': True},
    ]


async def test_repeated_poll_of_settled_sessions_counts_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """同一批已终态会话再次轮询时返回 0，不重复开启结算事务。"""
    ctx = _prepare(
        monkeypatch,
        {'sk-done': SimpleNamespace(session_key='sk-done')},
        {'sk-done': True},
    )
    ctx.fake_db.pending_rows = [('sk-done', 7)]

    first = await ctx.module.expire_practice_sessions()
    ctx.fake_db.pending_rows = []
    second = await ctx.module.expire_practice_sessions()

    assert first == {'settled': 1, 'failed': 0}
    assert second == {'settled': 0, 'failed': 0}
    assert ctx.fake_db.begin_calls == 1
    assert len(ctx.dao.calls) == 1
    assert ctx.fake_db.events == ['query', 'begin', 'commit', 'query']


async def test_already_terminal_session_is_not_recounted(monkeypatch: pytest.MonkeyPatch) -> None:
    """并发下仍被发现的已终态会话由 _expire_if_due 返回 False，统计保持为 0。"""
    ctx = _prepare(
        monkeypatch,
        {
            'sk-a': SimpleNamespace(session_key='sk-a'),
            'sk-b': SimpleNamespace(session_key='sk-b'),
        },
        {'sk-a': False, 'sk-b': False},
    )
    ctx.fake_db.pending_rows = [('sk-a', 1), ('sk-b', 2)]

    result = await ctx.module.expire_practice_sessions()

    assert result == {'settled': 0, 'failed': 0}
    assert ctx.fake_db.events == ['query', 'begin', 'commit', 'begin', 'commit']
    assert [call['for_update'] for call in ctx.dao.calls] == [True, True]


def test_beat_schedule_registers_qbank_v2_expire_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """beat 配置必须包含 V2 到期结算任务，且为 60 秒固定间隔。"""
    _install_fake_task_deps(monkeypatch)
    beat = _load_module(_BEAT_PATH, '_test_qbank_v2_beat_under_test')

    schedule = {item['task']: item['schedule'] for item in beat.get_local_beat_schedule().values()}

    assert _EXPECTED_TASK_NAME in schedule
    assert schedule[_EXPECTED_TASK_NAME] == pytest.approx(60.0)
