#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import IntEnum


class DeliveryStatus(IntEnum):
    """投递状态"""

    PENDING = 0
    SUCCESS = 1
    FAILED = 2
    RETRYING = 3


class EventLogStatus(IntEnum):
    """入站事件状态"""

    RECEIVED = 0
    PROCESSED = 1
    FAILED = 2


class InboundSource:
    """已知入站来源标识"""

    GITHUB = 'github'
    STRIPE = 'stripe'
    WECHAT_PAY = 'wechat_pay'
    GENERIC = 'generic'


# Standard Webhooks 时间戳容忍窗口 (秒)
TIMESTAMP_TOLERANCE = 300

# 重试间隔 (秒): 1min, 5min, 30min, 2h, 24h
RETRY_INTERVALS = [60, 300, 1800, 7200, 86400]

# 密钥前缀
SECRET_PREFIX = 'whsec_'

# ID 前缀
EVENT_ID_PREFIX = 'evt_'
ENDPOINT_ID_PREFIX = 'ep_'
DELIVERY_ID_PREFIX = 'dl_'

# 响应体截断大小 (10KB)
RESPONSE_BODY_MAX_LENGTH = 10240
