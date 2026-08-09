#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学习规划 CRUD 导出"""

from backend.app.study_plan.crud.crud_ability_profile import (
    study_ability_attempt_category_dao,
    study_ability_attempt_dao,
    study_ability_catalog_dao,
    study_ability_category_binding_dao,
    study_user_category_profile_dao,
    study_user_knowledge_profile_dao,
)
from backend.app.study_plan.crud.crud_item import study_plan_item_dao
from backend.app.study_plan.crud.crud_mentor import study_mentor_student_dao
from backend.app.study_plan.crud.crud_plan import study_plan_dao
from backend.app.study_plan.crud.crud_record import study_plan_record_dao
from backend.app.study_plan.crud.crud_spatial_cube import study_spatial_cube_pattern_dao
from backend.app.study_plan.crud.crud_template import (
    study_plan_template_dao,
    study_plan_template_item_dao,
)

__all__ = [
    'study_ability_attempt_category_dao',
    'study_ability_attempt_dao',
    'study_ability_catalog_dao',
    'study_ability_category_binding_dao',
    'study_mentor_student_dao',
    'study_plan_dao',
    'study_plan_item_dao',
    'study_plan_record_dao',
    'study_plan_template_dao',
    'study_plan_template_item_dao',
    'study_spatial_cube_pattern_dao',
    'study_user_category_profile_dao',
    'study_user_knowledge_profile_dao',
]
