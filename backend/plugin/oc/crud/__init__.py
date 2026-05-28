# oc crud
from backend.plugin.oc.crud.crud_campus_recruit import CRUDCampusRecruit, campus_recruit_dao
from backend.plugin.oc.crud.crud_intern_recruit import CRUDInternRecruit, intern_recruit_dao
from backend.plugin.oc.crud.crud_user_application import CRUDUserApplication, user_application_dao

__all__ = [
    # campus recruit
    'CRUDCampusRecruit',
    'campus_recruit_dao',
    # intern recruit
    'CRUDInternRecruit',
    'intern_recruit_dao',
    # user application
    'CRUDUserApplication',
    'user_application_dao',
]
