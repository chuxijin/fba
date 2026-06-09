#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

from pydantic import Field

from backend.app.study_plan.schema.item import GetStudyPlanItemDetail
from backend.app.study_plan.schema.plan import StudyPlanProgress
from backend.common.schema import SchemaBase


class TodayStudyPlanDetail(SchemaBase):
    """今日学习计划聚合视图"""

    plan_id: int = Field(description='所属计划 ID')
    plan_title: str = Field(description='计划标题')
    today: date = Field(description='当前日期')
    day_index: int = Field(ge=1, description='计划第几天')
    total_days: int = Field(ge=1, description='计划总天数')
    items: list[GetStudyPlanItemDetail] = Field(default_factory=list, description='今日计划项列表')
    progress: StudyPlanProgress = Field(description='今日完成进度')
