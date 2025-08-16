#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from .account import (
    SocialAccountBase,
    CreateSocialAccountParam,
    UpdateSocialAccountParam,
    GetSocialAccountDetail,
)
from .work import (
    SocialWorkBase,
    CreateSocialWorkParam,
    UpdateSocialWorkParam,
    GetSocialWorkDetail,
)
from .metric import (
    SocialWorkMetricBase,
    CreateSocialWorkMetricParam,
    UpdateSocialWorkMetricParam,
    GetSocialWorkMetricDetail,
)

__all__ = [
    # account
    "SocialAccountBase",
    "CreateSocialAccountParam",
    "UpdateSocialAccountParam",
    "GetSocialAccountDetail",
    # work
    "SocialWorkBase",
    "CreateSocialWorkParam",
    "UpdateSocialWorkParam",
    "GetSocialWorkDetail",
    # metric
    "SocialWorkMetricBase",
    "CreateSocialWorkMetricParam",
    "UpdateSocialWorkMetricParam",
    "GetSocialWorkMetricDetail",
]


