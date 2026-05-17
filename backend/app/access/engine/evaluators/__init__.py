#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.access.engine.evaluators.base import BaseEvaluator
from backend.app.access.engine.evaluators.direct_grant import DirectGrantEvaluator
from backend.app.access.engine.evaluators.free_pass import FreePassEvaluator
from backend.app.access.engine.evaluators.ownership import OwnershipEvaluator
from backend.app.access.engine.evaluators.quota_trial import QuotaTrialEvaluator
from backend.app.access.engine.evaluators.subscription_access import SubscriptionAccessEvaluator

DEFAULT_EVALUATORS: list[BaseEvaluator] = [
    FreePassEvaluator(),
    OwnershipEvaluator(),
    SubscriptionAccessEvaluator(),
    DirectGrantEvaluator(),
    QuotaTrialEvaluator(),
]

__all__ = [
    'DEFAULT_EVALUATORS',
    'BaseEvaluator',
    'DirectGrantEvaluator',
    'FreePassEvaluator',
    'OwnershipEvaluator',
    'QuotaTrialEvaluator',
    'SubscriptionAccessEvaluator',
]
