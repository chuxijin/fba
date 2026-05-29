#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import Field

from backend.app.access.schema.entitlement import GetMyEntitlement
from backend.app.access.schema.subscription import GetMySubscription
from backend.common.schema import SchemaBase


class GetMyAccessSummary(SchemaBase):
    """我的权益汇总"""

    subscriptions: list[GetMySubscription] = Field(default_factory=list, description='订阅列表')
    entitlements: list[GetMyEntitlement] = Field(default_factory=list, description='权益列表')
