# oc schemas
from backend.plugin.oc.schema.campus_recruit import (
    CampusRecruitSchemaBase,
    CreateCampusRecruitParam,
    GetCampusRecruitDetail,
    UpdateCampusRecruitParam,
)
from backend.plugin.oc.schema.crawler import CrawlerParam, CrawlerResult
from backend.plugin.oc.schema.intern_recruit import (
    CreateInternRecruitParam,
    GetInternRecruitDetail,
    InternRecruitSchemaBase,
    UpdateInternRecruitParam,
)
from backend.plugin.oc.schema.user_application import (
    CreateUserApplicationParam,
    GetUserApplicationDetail,
    UpdateUserApplicationParam,
    UserApplicationSchemaBase,
)

__all__ = [
    # campus recruit
    'CampusRecruitSchemaBase',
    'CreateCampusRecruitParam',
    'UpdateCampusRecruitParam',
    'GetCampusRecruitDetail',
    # intern recruit
    'InternRecruitSchemaBase',
    'CreateInternRecruitParam',
    'UpdateInternRecruitParam',
    'GetInternRecruitDetail',
    # user application
    'UserApplicationSchemaBase',
    'CreateUserApplicationParam',
    'UpdateUserApplicationParam',
    'GetUserApplicationDetail',
    # crawler
    'CrawlerParam',
    'CrawlerResult',
]
