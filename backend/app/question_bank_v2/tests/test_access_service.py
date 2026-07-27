import asyncio

from types import SimpleNamespace

import pytest

from backend.app.access.constants import ReasonCode, ResourceType
from backend.app.access.schema.engine import Decision
from backend.app.question_bank_v2.service import access_service as access_service_module
from backend.app.question_bank_v2.service.access_service import bank_access_service
from backend.common.exception import errors


def _make_bank(*, owner_id: int | None = None, visibility: str = 'public') -> SimpleNamespace:
    return SimpleNamespace(
        id=21,
        owner_id=owner_id,
        visibility=visibility,
        status='active',
        current_revision_id=31,
    )


def test_bank_access_uses_stable_bank_id_and_disables_trial(monkeypatch) -> None:
    """题库准入必须绑定稳定 bank_id 且完全禁用配额路径"""

    async def fake_get(*_args, **_kwargs):
        return _make_bank()

    captured: dict[str, object] = {}

    async def fake_decide(_db, ctx):
        captured['ctx'] = ctx
        return Decision.allow(reason_code=ReasonCode.SUBSCRIPTION_ACCESS)

    monkeypatch.setattr(access_service_module.bank_dao, 'get', fake_get)
    monkeypatch.setattr(access_service_module.access_decision_engine, 'decide', fake_decide)

    bank, decision = asyncio.run(bank_access_service.ensure_bank_access(db=None, user_id=7, bank_id=21))

    assert bank.id == 21
    assert decision.allowed
    ctx = captured['ctx']
    assert ctx.resource_type == ResourceType.QBANK
    assert ctx.resource_id == 21
    assert ctx.action == 'practice'
    assert not ctx.allow_trial
    assert not ctx.consume_trial


def test_bank_owner_bypasses_access_engine(monkeypatch) -> None:
    """私有题库所有者直接放行，不依赖运营权益规则"""

    async def fake_get(*_args, **_kwargs):
        return _make_bank(owner_id=7, visibility='private')

    async def fail_decide(*_args, **_kwargs):
        raise AssertionError('owner access must not call the decision engine')

    monkeypatch.setattr(access_service_module.bank_dao, 'get', fake_get)
    monkeypatch.setattr(access_service_module.access_decision_engine, 'decide', fail_decide)

    _, decision = asyncio.run(bank_access_service.ensure_bank_access(db=None, user_id=7, bank_id=21))

    assert decision.allowed
    assert decision.reason_code == ReasonCode.OWNERSHIP


def test_private_bank_rejects_non_owner_without_engine_fallback(monkeypatch) -> None:
    """私有题库不能因未配置资源规则而被引擎当作免费资源"""

    async def fake_get(*_args, **_kwargs):
        return _make_bank(owner_id=8, visibility='private')

    async def fail_decide(*_args, **_kwargs):
        raise AssertionError('private non-owner must not fall through to free resource')

    monkeypatch.setattr(access_service_module.bank_dao, 'get', fake_get)
    monkeypatch.setattr(access_service_module.access_decision_engine, 'decide', fail_decide)

    with pytest.raises(errors.ForbiddenError, match='没有此题库的刷题权限'):
        asyncio.run(bank_access_service.ensure_bank_access(db=None, user_id=7, bank_id=21))
