#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学习规划 schema 导出"""

from backend.app.study_plan.schema.ability import (
    BatchSubmitStudyAbilityAttemptParam,
    BatchSubmitStudyAbilityAttemptResult,
    CreateStudyAbilityCatalogParam,
    CreateStudyAbilityCategoryBindingParam,
    GetStudyAbilityCategoryBindingDetail,
    GetStudyAbilityAttemptDetail,
    GetStudyPlanAbilityCatalogItem,
    GetStudyUserCategoryProfileDetail,
    SubmitStudyAbilityAttemptParam,
    SubmitStudyAbilityAttemptResult,
    UpdateStudyAbilityCatalogParam,
    UpdateStudyAbilityCategoryBindingParam,
)
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
    GetMentorStudentOption,
    UpdateMentorStudentStatusParam,
)
from backend.app.study_plan.schema.plan import (
    CreateStudyPlanParam,
    GetStudyPlanDetail,
    StudyPlanProgress,
    UpdateStudyPlanParam,
)
from backend.app.study_plan.schema.practice_source import (
    PreviewStudyPlanPracticeSourceParam,
    PreviewStudyPlanPracticeSourceResult,
)
from backend.app.study_plan.schema.record import GetStudyPlanRecordDetail
from backend.app.study_plan.schema.recommendation import (
    GetStudyPlanItemRecommendation,
    RecommendationModuleType,
    StudyPlanItemRecommendationDraft,
)
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
    'BatchSubmitStudyAbilityAttemptParam',
    'BatchSubmitStudyAbilityAttemptResult',
    'CompleteStudyPlanItemParam',
    'CreateStudyAbilityCatalogParam',
    'CreateStudyAbilityCategoryBindingParam',
    'CreateStudyPlanItemParam',
    'CreateStudyPlanParam',
    'CreateStudyPlanTemplateItemParam',
    'CreateStudyPlanTemplateParam',
    'GetStudyAbilityCategoryBindingDetail',
    'GetStudyAbilityAttemptDetail',
    'GetStudyPlanAbilityCatalogItem',
    'GetMentorStudentDetail',
    'GetMentorStudentOption',
    'GetStudyPlanDetail',
    'GetStudyPlanItemDetail',
    'GetStudyPlanItemRecommendation',
    'GetStudyPlanRecordDetail',
    'GetStudyPlanTemplateDetail',
    'GetStudyPlanTemplateItemDetail',
    'GetStudyPlanTemplateWithItemsDetail',
    'GetStudyUserCategoryProfileDetail',
    'InstantiateStudyPlanTemplateParam',
    'PreviewStudyPlanPracticeSourceParam',
    'PreviewStudyPlanPracticeSourceResult',
    'RecommendationModuleType',
    'StartStudyPlanItemResult',
    'StudyPlanProgress',
    'StudyPlanItemRecommendationDraft',
    'SubmitStudyAbilityAttemptParam',
    'SubmitStudyAbilityAttemptResult',
    'TodayStudyPlanDetail',
    'UpdateMentorStudentStatusParam',
    'UpdateStudyAbilityCatalogParam',
    'UpdateStudyAbilityCategoryBindingParam',
    'UpdateStudyPlanItemParam',
    'UpdateStudyPlanParam',
    'UpdateStudyPlanTemplateParam',
]
