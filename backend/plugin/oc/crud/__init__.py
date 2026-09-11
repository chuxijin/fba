# oc crud
from backend.plugin.oc.crud.crud_company import CRUDOCCompany, oc_company_dao
from backend.plugin.oc.crud.crud_recruit_announcement import CRUDOCRecruitAnnouncement, recruit_announcement_dao
from backend.plugin.oc.crud.crud_user_application import CRUDUserApplication, user_application_dao

__all__ = [
    'CRUDOCCompany',
    'CRUDOCRecruitAnnouncement',
    'CRUDUserApplication',
    'oc_company_dao',
    'recruit_announcement_dao',
    'user_application_dao',
]
