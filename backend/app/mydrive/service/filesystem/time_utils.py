#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from backend.utils.timezone import timezone


def parse_timestamp(value: Any) -> datetime | None:
    """
    解析秒或毫秒时间戳。

    :param value: 原始时间戳
    :return:
    """
    if value is None or value == '':
        return None
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    if timestamp > 9_999_999_999:
        timestamp //= 1000
    return datetime.fromtimestamp(timestamp, tz=timezone.tz_info)
