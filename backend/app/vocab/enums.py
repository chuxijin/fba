#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import IntEnum, StrEnum


class CardState(IntEnum):
    """FSRS 卡片状态"""

    learning = 1
    review = 2
    relearning = 3


class Rating(IntEnum):
    """FSRS 用户评分"""

    again = 1
    hard = 2
    good = 3
    easy = 4


class ReviewMode(StrEnum):
    """学习模式"""

    recognize = 'recognize'
    self_eval = 'self_eval'
    spell = 'spell'
    listen = 'listen'


class BookCategory(StrEnum):
    """词书分类"""

    cet4 = 'cet4'
    cet6 = 'cet6'
    kaoyan = 'kaoyan'
    ielts = 'ielts'
    toefl = 'toefl'
    custom = 'custom'
