# oc schemas
from backend.plugin.oc.schema.company import (
    CompanyWebsiteParam,
    CreateCompanyParam,
    GetCompanyDetail,
    GetCompanyWebsiteDetail,
    OCCompanySchemaBase,
    UpdateCompanyParam,
)
from backend.plugin.oc.schema.crawler import CrawlerParam, CrawlerResult
from backend.plugin.oc.schema.recruit_announcement import (
    CreateRecruitAnnouncementParam,
    GetCompanyBriefDetail,
    GetRecruitAnnouncementDetail,
    GetRecruitAnnouncementWithCompanyDetail,
    OCRecruitAnnouncementSchemaBase,
    UpdateRecruitAnnouncementParam,
)
from backend.plugin.oc.schema.user_application import (
    CreateUserApplicationParam,
    GetApplicationAnnouncementDetail,
    GetUserApplicationDetail,
    GetUserApplicationWithRelationDetail,
    UpdateUserApplicationParam,
    UserApplicationSchemaBase,
)

__all__ = [
    'CompanyWebsiteParam',
    'CrawlerParam',
    'CrawlerResult',
    'CreateCompanyParam',
    'CreateRecruitAnnouncementParam',
    'CreateUserApplicationParam',
    'GetApplicationAnnouncementDetail',
    'GetCompanyBriefDetail',
    'GetCompanyDetail',
    'GetCompanyWebsiteDetail',
    'GetRecruitAnnouncementDetail',
    'GetRecruitAnnouncementWithCompanyDetail',
    'GetUserApplicationDetail',
    'GetUserApplicationWithRelationDetail',
    'OCCompanySchemaBase',
    'OCRecruitAnnouncementSchemaBase',
    'UpdateCompanyParam',
    'UpdateRecruitAnnouncementParam',
    'UpdateUserApplicationParam',
    'UserApplicationSchemaBase',
]
