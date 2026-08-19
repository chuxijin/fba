#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import StrEnum


class MemoryDeckScope(StrEnum):
    """卡组范围"""

    system = 'system'
    personal = 'personal'


class MemoryStatus(StrEnum):
    """卡组 / 卡片状态"""

    active = 'active'
    disabled = 'disabled'
    archived = 'archived'


class MemoryCardType(StrEnum):
    """卡片记忆玩法"""

    cloze = 'cloze'
    correction = 'correction'


class MemoryResponseMode(StrEnum):
    """卡片作答交互"""

    reveal = 'reveal'
    input = 'input'
    choice = 'choice'
    select_replace = 'select_replace'


class MemoryRevisionStatus(StrEnum):
    """卡片内容版本状态"""

    draft = 'draft'
    published = 'published'
    retired = 'retired'


class MemoryCheckResult(StrEnum):
    """客观判定结果"""

    correct = 'correct'
    wrong = 'wrong'
    undetermined = 'undetermined'


class MemorySubscriptionStatus(StrEnum):
    """用户卡组订阅状态"""

    active = 'active'
    paused = 'paused'


class MemoryUserStateStatus(StrEnum):
    """用户卡片记忆状态"""

    active = 'active'
    suspended = 'suspended'
