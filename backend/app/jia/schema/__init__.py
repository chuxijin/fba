#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.jia.schema.category import (
    CreateCategoryParam,
    DeleteCategoryParam,
    GetCategoryDetail,
    UpdateCategoryParam,
)
from backend.app.jia.schema.diaries import CreateDiaryParam, DeleteDiaryParam, GetDiaryDetail, UpdateDiaryParam
from backend.app.jia.schema.habits import (
    CreateHabitParam,
    CreateHabitRecordParam,
    DeleteHabitParam,
    DeleteHabitRecordParam,
    GetHabitDetail,
    GetHabitRecordDetail,
    UpdateHabitParam,
    UpdateHabitRecordParam,
)
from backend.app.jia.schema.note import (
    CreateNoteParam,
    DeleteNoteParam,
    GetNoteDetail,
    UpdateNoteParam,
)
from backend.app.jia.schema.reminders import CreateReminderParam, DeleteReminderParam, GetReminderDetail, UpdateReminderParam
from backend.app.jia.schema.tag import CreateTagParam, DeleteTagParam, GetTagDetail, UpdateTagParam

__all__ = [
    'CreateNoteParam',
    'UpdateNoteParam',
    'DeleteNoteParam',
    'GetNoteDetail',
    'CreateCategoryParam',
    'UpdateCategoryParam',
    'DeleteCategoryParam',
    'GetCategoryDetail',
    'CreateTagParam',
    'UpdateTagParam',
    'DeleteTagParam',
    'GetTagDetail',
    'CreateDiaryParam',
    'UpdateDiaryParam',
    'DeleteDiaryParam',
    'GetDiaryDetail',
    'CreateHabitParam',
    'UpdateHabitParam',
    'DeleteHabitParam',
    'GetHabitDetail',
    'CreateHabitRecordParam',
    'UpdateHabitRecordParam',
    'DeleteHabitRecordParam',
    'GetHabitRecordDetail',
    'CreateReminderParam',
    'UpdateReminderParam',
    'DeleteReminderParam',
    'GetReminderDetail',
]

