#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.coulddrive.schema.user import (
    BaseUserInfo,
    CreateDriveAccountParam,
    DriveAccountBase,
    GetDriveAccountDetail,
    GetUserFriendDetail,
    GetUserGroupDetail,
    UpdateDriveAccountParam,
)

from backend.app.coulddrive.schema.rule_template import (
    TemplateType,
    RuleTemplateBase,
    CreateRuleTemplateParam,
    UpdateRuleTemplateParam,
    GetRuleTemplateDetail,
    GetRuleTemplateListParam,
    RuleTemplateListItem,
    UseRuleTemplateParam,
    BatchDeleteRuleTemplateParam,
    RuleTemplateStatsDetail,
)

from backend.app.coulddrive.schema.resource import (
    ResourceBase,
    CreateResourceParam,
    UpdateResourceParam,
    GetResourceDetail,
    GetResourceListParam,
    ResourceListItem,
    ResourceStatistics,
)

from backend.app.coulddrive.schema.category import (
    CategoryBase,
    CreateCategoryParam,
    UpdateCategoryParam,
    GetCategoryDetail,
    GetCategoryListParam,
    CategoryListItem,
    CategoryTreeNode,
    GetCategoryTreeParam,
    CategoryOption,
    GetCategoryOptionsParam,
    CategoryStatistics,
    BatchUpdateCategoryStatusParam,
    BatchDeleteCategoryParam,
    MoveCategoryParam,
)
