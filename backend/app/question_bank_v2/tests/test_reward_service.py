import asyncio

from types import SimpleNamespace

from sqlalchemy.exc import SQLAlchemyError

from backend.app.question_bank_v2.service import reward_service as reward_module
from backend.app.question_bank_v2.service.reward_service import PracticeReward, practice_reward_service
from backend.utils.timezone import timezone


class _FakeDb:
    """奖励发放只依赖 begin_nested 的保存点语义"""

    def __init__(self) -> None:
        self.nested_count = 0

    def begin_nested(self) -> '_FakeDb':
        self.nested_count += 1
        return self

    async def __aenter__(self) -> '_FakeDb':
        return self

    async def __aexit__(self, *_exc_info) -> bool:
        return False


def _rule(**overrides) -> SimpleNamespace:
    rule = {
        'exp_delta': 1,
        'min_practice_count': 1,
        'min_practice_duration': 0,
    }
    rule.update(overrides)
    return SimpleNamespace(**rule)


def _patch_dependencies(
    monkeypatch,
    *,
    calls: list,
    rule: SimpleNamespace | None = None,
    progress: dict | None = None,
    add_error: Exception | None = None,
    total_duration_ms: int = 550_000,
) -> None:
    """把快照、规则查询、作答时长与经验写入换成可断言的 fake"""

    async def fake_snapshot_load(_db, **_kwargs):
        calls.append(('snapshot', {}))
        return SimpleNamespace(all_entitlement_codes={'vip:monthly'})

    async def fake_get_active_rule(_db, **kwargs):
        calls.append(('rule', kwargs))
        return rule

    async def fake_add(_db, **kwargs):
        calls.append(('add', kwargs))
        if add_error is not None:
            raise add_error
        return progress or {'total_exp': 12, 'available_exp': 12, 'current_grade': 2}

    async def fake_total_duration(_db, session_id):
        assert session_id == 115
        return total_duration_ms

    monkeypatch.setattr(reward_module.snapshot_service, 'load', fake_snapshot_load)
    monkeypatch.setattr(reward_module.experience_rule_dao, 'get_active_rule', fake_get_active_rule)
    monkeypatch.setattr(reward_module.experience_service, 'add_experience', fake_add)
    monkeypatch.setattr(reward_module.practice_response_dao, 'get_total_duration_ms', fake_total_duration)


def _grant(db: _FakeDb, **overrides) -> PracticeReward:
    params = {
        'user_id': 20,
        'session_id': 115,
        'answered_count': 16,
        'correct_count': 4,
    }
    params.update(overrides)
    return asyncio.run(practice_reward_service.grant_practice_correct_experience(db=db, **params))


def test_grant_practice_experience_by_correct_count(monkeypatch) -> None:
    """经验 = 规则单题经验 × 答对题数，并按权益快照匹配规则"""
    calls: list = []
    _patch_dependencies(monkeypatch, calls=calls, rule=_rule(exp_delta=2))

    reward = _grant(_FakeDb())

    assert reward.reward_exp == 8
    assert reward.practice_reward_exp == 8
    assert reward.check_in_reward_exp == 0
    assert reward.tier_grade == 2
    assert reward.exp == 12
    assert reward.available_exp == 12

    assert calls[0][0] == 'snapshot'
    assert calls[1] == ('rule', {'event_code': 'practice_correct', 'held_entitlement_codes': {'vip:monthly'}})
    assert calls[2][1] == {
        'user_id': 20,
        'exp_delta': 8,
        'source': 'practice_correct',
        'source_key': 'practice_correct:115',
        'reason': '完成练习答对 4 题奖励',
    }


def test_grant_skips_when_nothing_correct(monkeypatch) -> None:
    """全错不发经验，也不查规则"""
    calls: list = []
    _patch_dependencies(monkeypatch, calls=calls, rule=_rule())

    reward = _grant(_FakeDb(), correct_count=0)

    assert reward == PracticeReward()
    assert calls == []


def test_grant_skips_when_rule_missing(monkeypatch) -> None:
    """没有启用的 practice_correct 规则时静默跳过"""
    calls: list = []
    _patch_dependencies(monkeypatch, calls=calls, rule=None)

    reward = _grant(_FakeDb())

    assert reward == PracticeReward()
    assert [name for name, _ in calls] == ['snapshot', 'rule']


def test_grant_respects_min_practice_count(monkeypatch) -> None:
    """低于规则要求的最低做题数不发经验"""
    calls: list = []
    _patch_dependencies(monkeypatch, calls=calls, rule=_rule(min_practice_count=20))

    reward = _grant(_FakeDb())

    assert reward == PracticeReward()
    assert [name for name, _ in calls] == ['snapshot', 'rule']


def test_grant_respects_min_practice_duration(monkeypatch) -> None:
    """低于规则要求的最低练习时长不发经验（防刷）"""
    calls: list = []
    _patch_dependencies(
        monkeypatch,
        calls=calls,
        rule=_rule(min_practice_duration=600),
        total_duration_ms=120_000,
    )

    reward = _grant(_FakeDb())

    assert reward == PracticeReward()
    assert [name for name, _ in calls] == ['snapshot', 'rule']


def test_grant_failure_does_not_break_submit(monkeypatch) -> None:
    """发放失败只返回零值，不把异常抛给交卷主流程"""
    calls: list = []
    _patch_dependencies(monkeypatch, calls=calls, rule=_rule(), add_error=SQLAlchemyError('ledger down'))
    db = _FakeDb()

    reward = _grant(db)

    assert reward == PracticeReward()
    assert db.nested_count == 1
    assert [name for name, _ in calls] == ['snapshot', 'rule', 'add']


def test_resolve_granted_reward_reads_ledger(monkeypatch) -> None:
    """重复交卷按幂等键回查已发放经验，不再发放"""
    keys: list[str] = []

    async def fake_get_by_idempotency_key(_db, key):
        keys.append(key)
        return SimpleNamespace(exp_delta=4)

    async def fake_progress(_db, *, user_id):
        assert user_id == 20
        return {'total_exp': 4, 'available_exp': 4, 'current_grade': 1}

    monkeypatch.setattr(reward_module.growth_event_dao, 'get_by_idempotency_key', fake_get_by_idempotency_key)
    monkeypatch.setattr(reward_module.experience_service, 'get_user_progress', fake_progress)

    reward = asyncio.run(
        practice_reward_service.resolve_granted_practice_reward(db=_FakeDb(), user_id=20, session_id=115)
    )

    assert keys == ['exp_add:20:practice_correct:practice_correct:115']
    assert reward.reward_exp == 4
    assert reward.practice_reward_exp == 4
    assert reward.tier_grade == 1


def test_resolve_granted_reward_without_ledger(monkeypatch) -> None:
    """没有发放记录时返回零值（例如首次交卷就失败或命中门槛）"""

    async def fake_get_by_idempotency_key(_db, _key):
        return None

    monkeypatch.setattr(reward_module.growth_event_dao, 'get_by_idempotency_key', fake_get_by_idempotency_key)

    reward = asyncio.run(
        practice_reward_service.resolve_granted_practice_reward(db=_FakeDb(), user_id=20, session_id=115)
    )

    assert reward == PracticeReward()


def _patch_check_in(
    monkeypatch,
    *,
    calls: list,
    today_record=None,
    rule: SimpleNamespace | None = None,
    summary: dict | None = None,
    progress: dict | None = None,
    add_error: Exception | None = None,
    streak: tuple[int, int] = (0, 1),
) -> None:
    """把签到记录、今日练习摘要、签到规则与经验写入换成可断言的 fake"""
    streaks = list(streak)

    async def fake_get_by_user_and_date(_db, user_id, check_date):
        calls.append(('record', {'user_id': user_id, 'check_date': check_date}))
        return today_record

    async def fake_get_streak(_db, user_id):
        calls.append(('streak', {'user_id': user_id}))
        return streaks.pop(0) if len(streaks) > 1 else streaks[0]

    async def fake_check_in(_db, user_id, *, practice_count, practice_duration):
        calls.append(('check_in', {'user_id': user_id, 'count': practice_count, 'duration': practice_duration}))
        return SimpleNamespace(id=1)

    async def fake_snapshot_load(_db, **_kwargs):
        return SimpleNamespace(all_entitlement_codes=set())

    async def fake_get_active_rule(_db, **kwargs):
        calls.append(('rule', kwargs))
        return rule

    async def fake_summary(_db, *, user_id, since):
        calls.append(('summary', {'user_id': user_id, 'since': since}))
        return summary or {'practice_count': 5, 'duration_seconds': 300}

    async def fake_add(_db, **kwargs):
        calls.append(('add', kwargs))
        if add_error is not None:
            raise add_error
        return progress or {'total_exp': 6, 'available_exp': 6, 'current_grade': 1}

    async def fake_get_or_create(_db, user_id):
        return SimpleNamespace(id=9, streak_days=0)

    async def fake_update_model(_db, pk, data):
        calls.append(('sync_streak', {'pk': pk, 'data': data}))

    monkeypatch.setattr(reward_module.check_in_dao, 'get_by_user_and_date', fake_get_by_user_and_date)
    monkeypatch.setattr(reward_module.check_in_dao, 'get_streak', fake_get_streak)
    monkeypatch.setattr(reward_module.check_in_dao, 'check_in', fake_check_in)
    monkeypatch.setattr(reward_module.snapshot_service, 'load', fake_snapshot_load)
    monkeypatch.setattr(reward_module.experience_rule_dao, 'get_active_rule', fake_get_active_rule)
    monkeypatch.setattr(reward_module.practice_response_dao, 'get_today_practice_summary', fake_summary)
    monkeypatch.setattr(reward_module.experience_service, 'add_experience', fake_add)
    monkeypatch.setattr(reward_module.user_practice_stats_dao, 'get_or_create', fake_get_or_create)
    monkeypatch.setattr(reward_module.user_practice_stats_dao, 'update_model', fake_update_model)


def _auto_check_in(db: _FakeDb) -> PracticeReward:
    return asyncio.run(practice_reward_service.try_auto_check_in(db=db, user_id=20))


def test_auto_check_in_records_and_rewards(monkeypatch) -> None:
    """今日未签到且达到门槛时写打卡记录、发签到经验，并把连续天数同步到旧统计表"""
    calls: list = []
    _patch_check_in(monkeypatch, calls=calls, rule=_rule(exp_delta=2, min_practice_count=1))
    db = _FakeDb()

    reward = _auto_check_in(db)

    assert reward.reward_exp == 2
    assert reward.check_in_reward_exp == 2
    assert reward.is_auto_checked_in is True
    assert reward.check_in_streak == 1
    assert reward.tier_grade == 1
    assert reward.exp == 6

    assert ('check_in', {'user_id': 20, 'count': 5, 'duration': 300}) in calls
    assert ('sync_streak', {'pk': 9, 'data': {'streak_days': 1}}) in calls
    add_kwargs = next(payload for name, payload in calls if name == 'add')
    assert add_kwargs['exp_delta'] == 2
    assert add_kwargs['source'] == 'check_in'
    assert add_kwargs['source_key'] == f'check_in:20:{timezone.now().date().isoformat()}'
    assert db.nested_count == 1


def test_auto_check_in_skips_when_already_checked_in(monkeypatch) -> None:
    """当天已签到直接跳过，不写记录也不发经验"""
    calls: list = []
    _patch_check_in(monkeypatch, calls=calls, today_record=SimpleNamespace(id=1), rule=_rule(exp_delta=2))

    reward = _auto_check_in(_FakeDb())

    assert reward == PracticeReward()
    assert [name for name, _ in calls] == ['record']


def test_auto_check_in_skips_without_rule(monkeypatch) -> None:
    """没有启用的签到规则时跳过"""
    calls: list = []
    _patch_check_in(monkeypatch, calls=calls, rule=None)

    reward = _auto_check_in(_FakeDb())

    assert reward == PracticeReward()
    assert [name for name, _ in calls] == ['record', 'streak', 'rule']


def test_auto_check_in_respects_today_practice_count(monkeypatch) -> None:
    """今日做题数未达门槛不签到"""
    calls: list = []
    _patch_check_in(
        monkeypatch,
        calls=calls,
        rule=_rule(exp_delta=2, min_practice_count=10),
        summary={'practice_count': 3, 'duration_seconds': 300},
    )

    reward = _auto_check_in(_FakeDb())

    assert reward == PracticeReward()
    assert 'check_in' not in [name for name, _ in calls]
    assert 'add' not in [name for name, _ in calls]


def test_auto_check_in_respects_today_practice_duration(monkeypatch) -> None:
    """今日练习时长未达门槛不签到"""
    calls: list = []
    _patch_check_in(
        monkeypatch,
        calls=calls,
        rule=_rule(exp_delta=2, min_practice_duration=600),
        summary={'practice_count': 30, 'duration_seconds': 120},
    )

    reward = _auto_check_in(_FakeDb())

    assert reward == PracticeReward()
    assert 'check_in' not in [name for name, _ in calls]
    assert 'add' not in [name for name, _ in calls]


def test_auto_check_in_failure_does_not_break_submit(monkeypatch) -> None:
    """签到发放失败只返回零值，不把异常抛给交卷主流程"""
    calls: list = []
    _patch_check_in(monkeypatch, calls=calls, rule=_rule(exp_delta=2), add_error=SQLAlchemyError('ledger down'))
    db = _FakeDb()

    reward = _auto_check_in(db)

    assert reward == PracticeReward()
    assert db.nested_count == 1
    assert [name for name, _ in calls][-1] == 'add'


def test_resolve_check_in_reward_reads_ledger(monkeypatch) -> None:
    """重复交卷按当日幂等键回查签到经验，不重复签到"""
    calls: list = []
    _patch_check_in(monkeypatch, calls=calls, today_record=SimpleNamespace(id=1), streak=(1, 1))

    keys: list[str] = []

    async def fake_get_by_idempotency_key(_db, key):
        keys.append(key)
        return SimpleNamespace(exp_delta=2)

    async def fake_progress(_db, *, user_id):
        return {'total_exp': 6, 'available_exp': 6, 'current_grade': 1}

    monkeypatch.setattr(reward_module.growth_event_dao, 'get_by_idempotency_key', fake_get_by_idempotency_key)
    monkeypatch.setattr(reward_module.experience_service, 'get_user_progress', fake_progress)

    reward = asyncio.run(practice_reward_service.resolve_granted_check_in_reward(db=_FakeDb(), user_id=20))

    assert keys == [f'exp_add:20:check_in:check_in:20:{timezone.now().date().isoformat()}']
    assert reward.reward_exp == 2
    assert reward.check_in_reward_exp == 2
    assert reward.is_auto_checked_in is True
    assert reward.check_in_streak == 1


def test_resolve_check_in_reward_without_record(monkeypatch) -> None:
    """当天没有打卡记录时返回零值"""
    calls: list = []
    _patch_check_in(monkeypatch, calls=calls)

    reward = asyncio.run(practice_reward_service.resolve_granted_check_in_reward(db=_FakeDb(), user_id=20))

    assert reward == PracticeReward()
    assert [name for name, _ in calls] == ['record']
