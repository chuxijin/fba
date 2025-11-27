#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import IntEnum


class FoodType(IntEnum):
    """食物类型"""

    RAW = 0
    PROCESSED = 1


class ProcessingLevel(IntEnum):
    """加工程度"""

    UNPROCESSED = 0
    LIGHT = 1
    MEDIUM = 2
    DEEP = 3


class TagGroup(IntEnum):
    """标签分组"""

    HEALTH_ATTRIBUTE = 0
    DIET_PREFERENCE = 1
    CERTIFICATION = 2
