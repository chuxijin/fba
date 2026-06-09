#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学习规划 schema 导出"""

from backend.app.study_plan.schema.item import (
    CompleteStudyPlanItemParam,
    CreateStudyPlanItemParam,
    GetStudyPlanItemDetail,
    StartStudyPlanItemResult,
    UpdateStudyPlanItemParam,
)
from backend.app.study_plan.schema.mentor import (
    AssignMentorStudentParam,
    GetMentorStudentDetail,
    UpdateMentorStudentStatusParam,
)
from backend.app.study_plan.schema.plan import (
    CreateStudyPlanParam,
    GetStudyPlanDetail,
    StudyPlanProgress,
    UpdateStudyPlanParam,
)
from backend.app.study_plan.schema.record import GetStudyPlanRecordDetail
from backend.app.study_plan.schema.template import (
    CreateStudyPlanTemplateItemParam,
    CreateStudyPlanTemplateParam,
    GetStudyPlanTemplateDetail,
    GetStudyPlanTemplateItemDetail,
    GetStudyPlanTemplateWithItemsDetail,
    InstantiateStudyPlanTemplateParam,
    UpdateStudyPlanTemplateParam,
)
from backend.app.study_plan.schema.today import TodayStudyPlanDetail

__all__ = [
    'AssignMentorStudentParam',
    'CompleteStudyPlanItemParam',
    'CreateStudyPlanItemParam',
    'CreateStudyPlanParam',
    'CreateStudyPlanTemplateItemParam',
    'CreateStudyPlanTemplateParam',
    'GetMentorStudentDetail',
    'GetStudyPlanDetail',
    'GetStudyPlanItemDetail',
    'GetStudyPlanRecordDetail',
    'GetStudyPlanTemplateDetail',
    'GetStudyPlanTemplateItemDetail',
    'GetStudyPlanTemplateWithItemsDetail',
    'InstantiateStudyPlanTemplateParam',
    'StartStudyPlanItemResult',
    'StudyPlanProgress',
    'TodayStudyPlanDetail',
    'UpdateMentorStudentStatusParam',
    'UpdateStudyPlanItemParam',
    'UpdateStudyPlanParam',
    'UpdateStudyPlanTemplateParam',
]
