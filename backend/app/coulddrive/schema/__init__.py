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
