#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import Enum, IntEnum


class OpenAuthClientStatus(IntEnum):
    """开放平台客户端状态"""

    DISABLED = 0
    ENABLED = 1


class OpenAuthAuthorizationStatus(str, Enum):
    """用户与客户端的授权关系状态"""

    ACTIVE = 'active'
    REVOKED = 'revoked'
