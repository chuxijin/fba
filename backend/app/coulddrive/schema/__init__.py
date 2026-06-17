#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 分类使用 admin 的 schema
from backend.app.admin.schema.category import (
    CreateCategoryParam as CreateCategoryParam,
)
from backend.app.admin.schema.category import (
    DeleteCategoryParam as DeleteCategoryParam,
)
from backend.app.admin.schema.category import (
    GetCategoryDetail as GetCategoryDetail,
)
from backend.app.admin.schema.category import (
    GetCategoryTree as GetCategoryTree,
)
from backend.app.admin.schema.category import (
    UpdateCategoryParam as UpdateCategoryParam,
)
from backend.app.coulddrive.schema.resource import (
    CreateResourceParam as CreateResourceParam,
)
from backend.app.coulddrive.schema.resource import (
    GetResourceDetail as GetResourceDetail,
)
from backend.app.coulddrive.schema.resource import (
    GetResourceListParam as GetResourceListParam,
)
from backend.app.coulddrive.schema.resource import (
    ResourceBase as ResourceBase,
)
from backend.app.coulddrive.schema.resource import (
    ResourceListItem as ResourceListItem,
)
from backend.app.coulddrive.schema.resource import (
    ResourceStatistics as ResourceStatistics,
)
from backend.app.coulddrive.schema.resource import (
    UpdateResourceParam as UpdateResourceParam,
)
from backend.app.coulddrive.schema.rule_template import (
    BatchDeleteRuleTemplateParam as BatchDeleteRuleTemplateParam,
)
from backend.app.coulddrive.schema.rule_template import (
    CreateRuleTemplateParam as CreateRuleTemplateParam,
)
from backend.app.coulddrive.schema.rule_template import (
    GetRuleTemplateDetail as GetRuleTemplateDetail,
)
from backend.app.coulddrive.schema.rule_template import (
    GetRuleTemplateListParam as GetRuleTemplateListParam,
)
from backend.app.coulddrive.schema.rule_template import (
    RuleTemplateBase as RuleTemplateBase,
)
from backend.app.coulddrive.schema.rule_template import (
    RuleTemplateListItem as RuleTemplateListItem,
)
from backend.app.coulddrive.schema.rule_template import (
    RuleTemplateStatsDetail as RuleTemplateStatsDetail,
)
from backend.app.coulddrive.schema.rule_template import (
    TemplateType as TemplateType,
)
from backend.app.coulddrive.schema.rule_template import (
    UpdateRuleTemplateParam as UpdateRuleTemplateParam,
)
from backend.app.coulddrive.schema.rule_template import (
    UseRuleTemplateParam as UseRuleTemplateParam,
)
from backend.app.coulddrive.schema.user import (
    BaseUserInfo as BaseUserInfo,
)
from backend.app.coulddrive.schema.user import (
    CreateDriveAccountParam as CreateDriveAccountParam,
)
from backend.app.coulddrive.schema.user import (
    DriveAccountBase as DriveAccountBase,
)
from backend.app.coulddrive.schema.user import (
    GetDriveAccountDetail as GetDriveAccountDetail,
)
from backend.app.coulddrive.schema.user import (
    GetUserFriendDetail as GetUserFriendDetail,
)
from backend.app.coulddrive.schema.user import (
    GetUserGroupDetail as GetUserGroupDetail,
)
from backend.app.coulddrive.schema.user import (
    UpdateDriveAccountParam as UpdateDriveAccountParam,
)
