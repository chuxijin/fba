#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill 计算练习端点 wiring 测试：闸门 + service 透传 + 导出参数归一化"""

import asyncio
import importlib

import pytest

calculation_api = importlib.import_module('backend.app.skill.api.v1.calculation')
skill_service = importlib.import_module('backend.app.skill.service')
errors = importlib.import_module('backend.common.exception').errors


def test_generate_endpoints_raise_without_membership() -> None:
    """会员闸门拒绝时应抛 ForbiddenError，且不会调用生成服务"""
    calls = {'service': 0}

    async def fake_gate(_db, *, user_id, raise_on_deny=True):
        if raise_on_deny:
            raise errors.ForbiddenError(msg='使用公考 AI 助手需要开通会员')
        from backend.app.access.constants import ReasonCode
        from backend.app.access.schema.engine import Decision
        return Decision.deny(reason_code=ReasonCode.NO_MATCHING_GRANT)

    class _Svc:
        def generate_basic(self, *, obj):
            calls['service'] += 1

    monkeypatch_target = calculation_api
    original = monkeypatch_target.ensure_skill_access
    monkeypatch_target.ensure_skill_access = fake_gate
    original_service = monkeypatch_target.calculation_practice_service
    monkeypatch_target.calculation_practice_service = _Svc()
    try:
        with pytest.raises(Exception) as exc_info:
            asyncio.run(
                calculation_api.skill_generate_basic(
                    db=None,
                    identity=_identity(),
                    obj=_basic_param(),
                )
            )
        assert '会员' in str(exc_info.value)
        assert calls['service'] == 0
    finally:
        monkeypatch_target.ensure_skill_access = original
        monkeypatch_target.calculation_practice_service = original_service


def test_generate_basic_passes_gate_and_service() -> None:
    """会员放行时应调用生成服务并返回其结果"""
    from backend.app.gongkao.schema.calculation_practice import BasicCalculationSession, PerformanceThresholds

    session = BasicCalculationSession(
        generator_version='test',
        seed=42,
        count=0,
        questions=[],
        type_key='custom',
        performance_thresholds=PerformanceThresholds(excellent=10, good=20, **{'pass': 30}),
    )

    async def fake_gate(_db, *, user_id, raise_on_deny=True):
        return None

    calls = {'service': 0}
    api = calculation_api
    original_gate, original_svc = api.ensure_skill_access, api.calculation_practice_service

    class _SvcWithCounter:
        def generate_basic(self, *, obj):
            calls['service'] += 1
            return session

    api.ensure_skill_access = fake_gate
    api.calculation_practice_service = _SvcWithCounter()
    try:
        result = asyncio.run(
            api.skill_generate_basic(db=None, identity=_identity(), obj=_basic_param())
        )
        assert calls['service'] == 1
        assert result.data is session
    finally:
        api.ensure_skill_access = original_gate
        api.calculation_practice_service = original_svc


def test_regenerate_questions_basic_deterministic() -> None:
    """basic 重生成应输出 render_book 消费结构且含题号"""
    from backend.app.gongkao.schema.calculation_practice import GenerateBasicCalculationParam

    param = GenerateBasicCalculationParam(type_key='custom', count=3, seed=7)
    questions = calculation_api._regenerate_questions(
        type('Obj', (), {'kind': 'basic', 'params': param.model_dump()})()
    )
    assert len(questions) == 3
    assert questions[0]['number'] == 1
    assert questions[0]['section_title'] == '基础计算'
    assert 'expression' in questions[0] and 'answer' in questions[0]


def test_regenerate_questions_advanced_deterministic() -> None:
    """advanced 重生成应把材料+问题拼为 expression，answer 取 answer_text"""
    from backend.app.gongkao.schema.calculation_practice import GenerateAdvancedCalculationParam

    param = GenerateAdvancedCalculationParam(method='scaling_div', count=2, seed=9)
    questions = calculation_api._regenerate_questions(
        type('Obj', (), {'kind': 'advanced', 'params': param.model_dump()})()
    )
    assert len(questions) == 2
    assert questions[0]['section_title'] == '进阶速算'
    assert questions[0]['expression']
    assert questions[0]['answer'] != ''


def _identity():
    from backend.plugin.openauth.schema.authorization import GetOpenAuthCheckResult
    from backend.utils.timezone import timezone

    return GetOpenAuthCheckResult(
        user_id=1,
        client_id='oac_gongkao_cli_dev',
        scopes=['skill:use'],
        authorized=True,
        expires_at=timezone.now(),
    )


def _basic_param():
    from backend.app.gongkao.schema.calculation_practice import GenerateBasicCalculationParam

    return GenerateBasicCalculationParam(type_key='custom', count=3, seed=7)
