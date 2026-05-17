#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from backend.app.access.constants import CycleType
from backend.utils.timezone import timezone


def build_cycle_key(cycle_type: str, ts: datetime | None = None) -> str:
    """
    根据周期类型生成周期键

    :param cycle_type: 周期类型
    :param ts: 参考时间, 空则取当前时间
    :return:
    """
    now = ts or timezone.now()
    if cycle_type == CycleType.DAILY:
        return now.strftime('%Y-%m-%d')
    if cycle_type == CycleType.WEEKLY:
        return now.strftime('%G-W%V')
    if cycle_type == CycleType.MONTHLY:
        return now.strftime('%Y-%m')
    if cycle_type == CycleType.YEARLY:
        return now.strftime('%Y')
    if cycle_type == CycleType.LIFETIME:
        return 'lifetime'
    raise ValueError(f'unsupported cycle type: {cycle_type}')
