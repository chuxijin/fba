import asyncio

from typing import Any, cast

from backend.app.access.engine.evaluators.quota_trial import QuotaTrialEvaluator
from backend.app.access.schema.engine import AccessContext, ExplanationNode


def test_quota_trial_evaluator_can_be_disabled_for_access_only_resource() -> None:
    """纯准入资源即使存在 trial 规则也不进入配额查询或扣减"""
    explanation: list[ExplanationNode] = []
    context = AccessContext(
        user_id=7,
        resource_type='qbank',
        resource_id=21,
        allow_trial=False,
        consume_trial=False,
    )

    result = asyncio.run(
        QuotaTrialEvaluator().evaluate(
            cast(Any, None),
            context,
            cast(Any, [object()]),
            cast(Any, object()),
            explanation,
        )
    )

    assert result is None
    assert explanation[-1].outcome == 'pass'
    assert explanation[-1].reason == '当前业务不允许使用试看配额'
