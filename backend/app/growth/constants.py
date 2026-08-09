#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import Enum


class GrowthEventOp(str, Enum):
    """成长事件操作类型"""

    CREDIT = 'credit'
    CONSUME = 'consume'
    RESET = 'reset'
    ADJUST = 'adjust'


# 等级阈值: {等级: 达到该等级所需累计经验}
# 等比数列 ratio=1.4, 10 级累计 5000
TIER_THRESHOLDS: dict[int, int] = {
    1: 72,
    2: 172,
    3: 312,
    4: 509,
    5: 784,
    6: 1169,
    7: 1708,
    8: 2463,
    9: 3520,
    10: 5000,
}

TIER_MAX_GRADE = max(TIER_THRESHOLDS)


def resolve_grade(total_exp: int) -> int:
    """根据累计经验计算当前等级"""
    grade = 0
    for g, threshold in sorted(TIER_THRESHOLDS.items()):
        if total_exp >= threshold:
            grade = g
        else:
            break
    return grade


def next_tier_exp_required(current_grade: int) -> int | None:
    """返回下一级所需累计经验, 已满级返回 None"""
    next_grade = current_grade + 1
    return TIER_THRESHOLDS.get(next_grade)
