#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill 业务薄层测试：会员闸门 / 资格查询 / API 装配"""

import asyncio
import importlib

import pytest

from backend.app.access.constants import ReasonCode
from backend.app.access.schema.engine import Decision

skill_service = importlib.import_module('backend.app.skill.service')
resource_access_service_module = importlib.import_module('backend.app.access.service.resource_access_service')


def test_skill_access_profile_registered() -> None:
    """内置 skill 权益档案应完成注册并可检索"""
    from backend.app.access.service.resource_profile_registry import access_profile_registry

    profile = access_profile_registry.get(skill_service.GONGKAO_SKILL_USE_PROFILE_CODE)
    assert profile is not None
    assert profile.resource_type == 'skill'
    assert profile.action == 'access'


def test_ensure_skill_access_denies_without_entitlement(monkeypatch) -> None:
    """无权益时应拒绝并抛 ForbiddenError"""
    from backend.common.exception import errors

    async def fake_decide(_db, *, profile_code, user_id, consume_trial=False, raise_on_deny=True):
        assert profile_code == skill_service.GONGKAO_SKILL_USE_PROFILE_CODE
        assert user_id == 9
        if raise_on_deny:
            raise errors.ForbiddenError(msg='使用公考 AI 助手需要开通会员')
        return Decision.deny(reason_code=ReasonCode.NO_MATCHING_GRANT)

    monkeypatch.setattr(skill_service.resource_access_service, 'decide', fake_decide)

    with pytest.raises(errors.ForbiddenError, match='需要开通会员'):
        asyncio.run(skill_service.ensure_skill_access(None, user_id=9))


def test_get_skill_entitlement_status_returns_deny_message(monkeypatch) -> None:
    """资格查询不拦截，返回 (False, 引导文案) 供 CLI 展示"""
    async def fake_decide(_db, *, profile_code, user_id, consume_trial=False, raise_on_deny=True):
        return Decision.deny(reason_code=ReasonCode.NO_MATCHING_GRANT)

    monkeypatch.setattr(skill_service.resource_access_service, 'decide', fake_decide)

    can_use, message = asyncio.run(skill_service.get_skill_entitlement_status(None, user_id=9))
    assert can_use is False
    assert message == '使用公考 AI 助手需要开通会员'


def test_get_skill_entitlement_status_allows_member(monkeypatch) -> None:
    """持权益会员应返回 (True, None)"""
    async def fake_decide(_db, *, profile_code, user_id, consume_trial=False, raise_on_deny=True):
        return Decision.allow(reason_code=ReasonCode.SUBSCRIPTION_ACCESS)

    monkeypatch.setattr(skill_service.resource_access_service, 'decide', fake_decide)

    can_use, message = asyncio.run(skill_service.get_skill_entitlement_status(None, user_id=9))
    assert can_use is True
    assert message is None
