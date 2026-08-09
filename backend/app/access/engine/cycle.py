#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

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


def build_cycle_end(cycle_type: str, ts: datetime | None = None) -> datetime | None:
    """
    计算周期结束时刻(开区间上界), 用作订阅补账额度包的过期时间

    周期额度包在周期结束时自然失效, 因此扣减时按 expires_at 升序优先消耗,
    即可实现"优先扣即将失效的配额"。LIFETIME 返回 None 表示永不过期。

    :param cycle_type: 周期类型
    :param ts: 参考时间, 空则取当前时间
    :return:
    """
    if cycle_type == CycleType.LIFETIME:
        return None

    now = ts or timezone.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if cycle_type == CycleType.DAILY:
        return day_start + timedelta(days=1)
    if cycle_type == CycleType.WEEKLY:
        # ISO 周以周一为起点, isoweekday() 周一为 1, 周日为 7
        return day_start + timedelta(days=8 - day_start.isoweekday())
    if cycle_type == CycleType.MONTHLY:
        if day_start.month == 12:
            return day_start.replace(year=day_start.year + 1, month=1, day=1)
        return day_start.replace(month=day_start.month + 1, day=1)
    if cycle_type == CycleType.YEARLY:
        return day_start.replace(year=day_start.year + 1, month=1, day=1)
    raise ValueError(f'unsupported cycle type: {cycle_type}')
