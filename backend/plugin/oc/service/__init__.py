# oc services
from backend.plugin.oc.service.campus_recruit_service import CampusRecruitService, campus_recruit_service
from backend.plugin.oc.service.intern_recruit_service import InternRecruitService, intern_recruit_service
from backend.plugin.oc.service.user_application_service import UserApplicationService, user_application_service

__all__ = [
    # campus recruit
    'CampusRecruitService',
    'campus_recruit_service',
    # intern recruit
    'InternRecruitService',
    'intern_recruit_service',
    # user application
    'UserApplicationService',
    'user_application_service',
]
