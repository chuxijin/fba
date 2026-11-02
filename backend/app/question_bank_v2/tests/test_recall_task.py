"""V2 复盘回测提醒定时任务回归测试：
- notify_practice_due 分页 after keyset 全量扫描
- 一个用户异常独立事务 rollback 不影响下一个用户 commit
- 重试同日不重复发送（幂等性）
- 返回 sent / failed 计数精确统计
- now 变量冻结传递与锁/隔离机制验证

全部依赖使用内存 fake / mock，完全阻断真实的 DB / Redis / Celery / 网络连接。
直接测试 tasks.py 中的 notify_practice_due 真实实现。
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types

from datetime import datetime, timezone
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

_EXPECTED_NOTIFY_TASK_NAME = 'qbank_v2:notify_practice_due'


class _FakeCeleryApp:
    def __init__(self) -> None:
        self.task_names: list[str] = []

    def task(self, *args: Any, **kwargs: Any) -> Any:
        task_name = kwargs.get('name')

        def decorator(func: Any) -> Any:
            self.task_names.append(task_name)
            return func

        return decorator


class _FakeCrontab:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs


def _install_fake_task_deps(monkeypatch: pytest.MonkeyPatch) -> _FakeCeleryApp:
    fake_celery = types.ModuleType('backend.app.task.celery')
    fake_app = _FakeCeleryApp()
    fake_celery.celery_app = fake_app
    monkeypatch.setitem(sys.modules, 'backend.app.task.celery', fake_celery)

    fake_crontab = types.ModuleType('backend.app.task.utils.tzcrontab')
    fake_crontab.TzAwareCrontab = _FakeCrontab
    monkeypatch.setitem(sys.modules, 'backend.app.task.utils.tzcrontab', fake_crontab)
    return fake_app


def _load_module(path: Path, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _DiscoveryContext:
    def __init__(self, owner: _FakeAsyncDB) -> None:
        self.owner = owner

    async def __aenter__(self) -> _DiscoveryDB:
        self.owner.events.append('discovery_enter')
        return _DiscoveryDB(self.owner)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        self.owner.events.append('discovery_exit')
        return False


class _DiscoveryDB:
    def __init__(self, owner: _FakeAsyncDB) -> None:
        self.owner = owner


class _TransactionContext:
    def __init__(self, owner: _FakeAsyncDB) -> None:
        self.owner = owner

    async def __aenter__(self) -> SimpleNamespace:
        self.owner.events.append('tx_begin')
        return SimpleNamespace()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        self.owner.events.append('tx_rollback' if exc_type is not None else 'tx_commit')
        return False


class _FakeAsyncDB:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.begin_calls = 0

    def __call__(self) -> _DiscoveryContext:
        return _DiscoveryContext(self)

    def begin(self) -> _TransactionContext:
        self.begin_calls += 1
        return _TransactionContext(self)


def _ignore_exception(*args: Any, **kwargs: Any) -> None:
    pass


class _TaskTestEnv:
    def __init__(
        self,
        module: types.ModuleType,
        fake_app: _FakeCeleryApp,
        fake_db: _FakeAsyncDB,
        candidate_mock: AsyncMock,
        notify_mock: AsyncMock,
        fixed_now: datetime,
    ) -> None:
        self.module = module
        self.fake_app = fake_app
        self.fake_db = fake_db
        self.candidate_mock = candidate_mock
        self.notify_mock = notify_mock
        self.fixed_now = fixed_now


def _prepare_env(monkeypatch: pytest.MonkeyPatch) -> _TaskTestEnv:
    fake_app = _install_fake_task_deps(monkeypatch)
    tasks = _load_module(_TASKS_PATH, '_test_qbank_v2_recall_task_under_test')
    monkeypatch.setattr(tasks, 'log', SimpleNamespace(exception=_ignore_exception))

    fake_db = _FakeAsyncDB()
    monkeypatch.setattr(tasks, 'async_db_session', fake_db)

    fixed_now = datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)
    fake_tz = SimpleNamespace(now=lambda: fixed_now)
    monkeypatch.setattr(tasks, 'timezone', fake_tz)

    candidate_mock = AsyncMock()
    notify_mock = AsyncMock()
    monkeypatch.setattr(tasks.qbank_notification_service, 'candidate_users', candidate_mock)
    monkeypatch.setattr(tasks.qbank_notification_service, 'notify_practice_due', notify_mock)

    return _TaskTestEnv(
        module=tasks,
        fake_app=fake_app,
        fake_db=fake_db,
        candidate_mock=candidate_mock,
        notify_mock=notify_mock,
        fixed_now=fixed_now,
    )


@pytest.mark.asyncio
async def test_notify_practice_due_keyset_pagination_full_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 notify_practice_due 分页 after keyset 全量扫描，直到空列表停止。"""
    env = _prepare_env(monkeypatch)

    batches = {
        0: [101, 102],
        102: [103, 104],
        104: [],
    }

    async def candidate_side_effect(db: Any, *, after: int, now: datetime) -> list[int]:
        await asyncio.sleep(0)
        assert now == env.fixed_now
        return batches.get(after, [])

    env.candidate_mock.side_effect = candidate_side_effect
    env.notify_mock.return_value = True

    result = await env.module.notify_practice_due()

    assert result == {'sent': 4, 'failed': 0}
    assert env.candidate_mock.call_count == 3
    candidate_calls = env.candidate_mock.call_args_list
    assert candidate_calls[0].kwargs['after'] == 0
    assert candidate_calls[1].kwargs['after'] == 102
    assert candidate_calls[2].kwargs['after'] == 104

    # 4 个用户各自调了 1 次 notify
    assert env.notify_mock.call_count == 4
    notified_users = [call.kwargs['user_id'] for call in env.notify_mock.call_args_list]
    assert notified_users == [101, 102, 103, 104]
    # 所有用户都使用同个全局固定 now
    assert all(call.kwargs['now'] == env.fixed_now for call in env.notify_mock.call_args_list)


@pytest.mark.asyncio
async def test_notify_practice_due_user_exception_isolation_rollback(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证单个用户异常独立事务 rollback，不中断循环，下一个用户独立 commit。"""
    env = _prepare_env(monkeypatch)

    async def candidate_side_effect(db: Any, *, after: int, now: datetime) -> list[int]:
        await asyncio.sleep(0)
        return [1, 2, 3] if after == 0 else []

    env.candidate_mock.side_effect = candidate_side_effect

    async def notify_side_effect(*, db: Any, user_id: int, now: datetime) -> bool:
        await asyncio.sleep(0)
        if user_id == 2:
            raise RuntimeError('user 2 DB crash')
        return True

    env.notify_mock.side_effect = notify_side_effect

    result = await env.module.notify_practice_due()

    # user 1: sent=True, user 2: failed(exception -> None), user 3: sent=True
    assert result == {'sent': 2, 'failed': 1}
    assert env.notify_mock.call_count == 3

    # 事件流：discovery 1 次 -> user1 commit -> user2 rollback -> user3 commit -> discovery 空
    expected_events = [
        'discovery_enter',
        'discovery_exit',
        'tx_begin',
        'tx_commit',
        'tx_begin',
        'tx_rollback',
        'tx_begin',
        'tx_commit',
        'discovery_enter',
        'discovery_exit',
    ]
    assert env.fake_db.events == expected_events


@pytest.mark.asyncio
async def test_notify_practice_due_same_day_retry_no_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证重试时同日不重复发送（service 返回 False 时不计入 sent 也不计入 failed）。"""
    env = _prepare_env(monkeypatch)

    async def candidate_side_effect(db: Any, *, after: int, now: datetime) -> list[int]:
        await asyncio.sleep(0)
        return [10] if after == 0 else []

    # 第一次运行：用户 10 发送成功
    env.candidate_mock.side_effect = candidate_side_effect
    env.notify_mock.return_value = True

    first_run = await env.module.notify_practice_due()
    assert first_run == {'sent': 1, 'failed': 0}

    # 第二次运行（同日再次触发）：service 内部幂等拦截，notify_practice_due 返回 False
    env.fake_db.events.clear()
    env.notify_mock.return_value = False

    second_run = await env.module.notify_practice_due()
    # 返回 False 时，既不是 sent 增加，也不是 failed 增加
    assert second_run == {'sent': 0, 'failed': 0}
    assert env.fake_db.events == [
        'discovery_enter',
        'discovery_exit',
        'tx_begin',
        'tx_commit',
        'discovery_enter',
        'discovery_exit',
    ]


@pytest.mark.asyncio
async def test_notify_practice_due_counts_and_now_consistency(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 sent/failed 混合计数精确返回，以及一轮任务中多批 keyset 间 now 变量保持同一时间戳。"""
    env = _prepare_env(monkeypatch)

    now_samples: list[datetime] = []

    # 2 个批次：[201, 202] -> [203] -> []
    async def candidate_side_effect(db: Any, *, after: int, now: datetime) -> list[int]:
        await asyncio.sleep(0)
        now_samples.append(now)
        if after == 0:
            return [201, 202]
        if after == 202:
            return [203]
        return []

    async def notify_side_effect(*, db: Any, user_id: int, now: datetime) -> bool:
        await asyncio.sleep(0)
        now_samples.append(now)
        if user_id == 201:
            return True  # 成功发送
        if user_id == 202:
            return False  # 已发送过或未达触发条件
        if user_id == 203:
            raise ValueError('Third user failed unexpectedly')
        return False

    env.candidate_mock.side_effect = candidate_side_effect
    env.notify_mock.side_effect = notify_side_effect

    result = await env.module.notify_practice_due()

    assert result == {'sent': 1, 'failed': 1}
    # 检查所有采样到的 now 都是 env.fixed_now 实例，任务生命周期内 now 保持冻结
    assert len(now_samples) == 6  # 3 candidate calls + 3 notify calls
    assert all(sample is env.fixed_now for sample in now_samples)
