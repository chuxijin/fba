from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock

import pytest

from backend.app.access.constants import ReasonCode
from backend.app.access.schema.engine import Decision
from backend.app.access.service.resource_profiles import AGENT_SHENLUN_GRADE_PROFILE_CODE
from backend.plugin.agent.service.access import quota as quota_module
from backend.plugin.agent.service.access.quota import AgentQuotaService, agent_quota_service
from backend.plugin.agent.service.shenlun_service import ShenlunGradingService


@pytest.mark.asyncio
async def test_shenlun_quota_consume_uses_stable_run_source_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = Decision.allow(reason_code=ReasonCode.TRIAL_POLICY, trial_mode='daily_count')
    db = object()

    consume = AsyncMock(return_value=expected)
    monkeypatch.setattr(quota_module.resource_access_service, 'consume', consume)

    result = await agent_quota_service.consume_shenlun_grading(db=db, user_id=9, run_id=123)

    assert result is expected
    consume.assert_awaited_once_with(
        db,
        profile_code=AGENT_SHENLUN_GRADE_PROFILE_CODE,
        user_id=9,
        source_ref='shenlun_grading_run:123',
    )


def test_quota_decision_round_trip_keeps_ledger_reference() -> None:
    decision = Decision.allow(
        reason_code=ReasonCode.METERED_CONSUMED,
        matched_grant='ai.agent.shenlun.quota',
        consumed_ledger_id=456,
    )

    state = AgentQuotaService.acquired_state(run_id=12, decision=decision)
    restored = AgentQuotaService.restore_decision(state)

    assert restored is not None
    assert restored.consumed_ledger_id == 456
    assert restored.matched_grant == 'ai.agent.shenlun.quota'


@pytest.mark.asyncio
async def test_failed_metered_run_refunds_and_closes_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = Decision.allow(
        reason_code=ReasonCode.METERED_CONSUMED,
        matched_grant='ai.agent.shenlun.quota',
        consumed_ledger_id=789,
    )
    run = SimpleNamespace(
        id=44,
        user_id=7,
        config_snapshot={
            'quota': AgentQuotaService.acquired_state(run_id=44, decision=decision),
        },
    )
    refund = AsyncMock()
    monkeypatch.setattr(agent_quota_service, 'refund_shenlun_grading', refund)

    await ShenlunGradingService._refund_quota(db=object(), run=run)

    refund.assert_awaited_once_with(db=ANY, user_id=7, run_id=44, decision=decision)
    assert run.config_snapshot['quota']['status'] == 'refunded'


def test_retry_config_does_not_inherit_previous_quota_state() -> None:
    config = ShenlunGradingService._retry_config({
        'model_name': 'gpt-5.4',
        'quota': {'status': 'refunded'},
    })

    assert config == {'model_name': 'gpt-5.4'}


@pytest.mark.asyncio
async def test_failed_daily_trial_run_is_marked_refunded(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = Decision.allow(
        reason_code=ReasonCode.TRIAL_POLICY,
        trial_mode='daily_count',
        trial_counter_key='trial-counter',
        trial_idempotency_key='trial-source',
    )
    run = SimpleNamespace(
        id=45,
        user_id=8,
        config_snapshot={'quota': AgentQuotaService.acquired_state(run_id=45, decision=decision)},
    )
    monkeypatch.setattr(agent_quota_service, 'refund_shenlun_grading', AsyncMock())

    await ShenlunGradingService._refund_quota(db=object(), run=run)

    assert run.config_snapshot['quota']['status'] == 'refunded'
