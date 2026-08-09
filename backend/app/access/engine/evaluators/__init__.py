#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.access.engine.evaluators.base import BaseEvaluator
from backend.app.access.engine.evaluators.direct_grant import DirectGrantEvaluator
from backend.app.access.engine.evaluators.free_pass import FreePassEvaluator
from backend.app.access.engine.evaluators.metered import MeteredEvaluator
from backend.app.access.engine.evaluators.subscription_access import SubscriptionAccessEvaluator
from backend.app.access.engine.evaluators.trial_policy import TrialPolicyEvaluator

# 顺序即优先级: 限免 > 订阅准入 > 运营直授 > 计量配额 > 试看兜底
DEFAULT_EVALUATORS: list[BaseEvaluator] = [
    FreePassEvaluator(),
    SubscriptionAccessEvaluator(),
    DirectGrantEvaluator(),
    MeteredEvaluator(),
    TrialPolicyEvaluator(),
]

__all__ = [
    'DEFAULT_EVALUATORS',
    'BaseEvaluator',
    'DirectGrantEvaluator',
    'FreePassEvaluator',
    'MeteredEvaluator',
    'SubscriptionAccessEvaluator',
    'TrialPolicyEvaluator',
]
