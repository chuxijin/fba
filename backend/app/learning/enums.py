from enum import StrEnum


class LearningPlanSource(StrEnum):
    system = 'system'
    user = 'user'
    admin_custom = 'admin_custom'
    ai = 'ai'


class LearningPlanStatus(StrEnum):
    draft = 'draft'
    active = 'active'
    paused = 'paused'
    completed = 'completed'
    archived = 'archived'


class LearningTemplateStatus(StrEnum):
    draft = 'draft'
    active = 'active'
    archived = 'archived'


class LearningDeliverySource(StrEnum):
    external_order = 'external_order'
    manual = 'manual'
    gift = 'gift'
    internal = 'internal'
    other = 'other'


class LearningDeliveryStatus(StrEnum):
    pending = 'pending'
    drafting = 'drafting'
    validated = 'validated'
    delivered = 'delivered'
    canceled = 'canceled'


class LearningActionType(StrEnum):
    learn = 'learn'
    read = 'read'
    practice = 'practice'
    wrong_review = 'wrong_review'
    ability = 'ability'
    review = 'review'
    custom = 'custom'


class LearningResourceType(StrEnum):
    content = 'content'
    course = 'course'
    course_lesson = 'course_lesson'
    question_bank = 'question_bank'
    ability = 'ability'
    external = 'external'
    none = 'none'


class LearningTaskStatus(StrEnum):
    pending = 'pending'
    in_progress = 'in_progress'
    completed = 'completed'
    skipped = 'skipped'
    canceled = 'canceled'


class LearningFocusMode(StrEnum):
    pomodoro = 'pomodoro'
    countdown = 'countdown'
    stopwatch = 'stopwatch'


class LearningFocusStatus(StrEnum):
    running = 'running'
    paused = 'paused'
    completed = 'completed'
    canceled = 'canceled'
