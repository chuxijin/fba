#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import Enum


class GrowthEventOp(str, Enum):
    """成长事件操作类型"""

    CREDIT = 'credit'
    CONSUME = 'consume'
    RESET = 'reset'
    ADJUST = 'adjust'


class FamilyCode(str, Enum):
    """成长族群"""

    FREE = 'FREE'
    VIP = 'VIP'
    SVIP = 'SVIP'


DEFAULT_FAMILY = FamilyCode.FREE.value
