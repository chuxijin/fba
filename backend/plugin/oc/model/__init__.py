# oc models
from backend.plugin.oc.model.company import OCCompany, OCCompanyWebsite, OCRecruitAnnouncement
from backend.plugin.oc.model.formatter import FormatterEmbedding, FormatterField, FormatterMapping
from backend.plugin.oc.model.resource import OCResource
from backend.plugin.oc.model.user_application import UserApplication

__all__ = [
    'FormatterEmbedding',
    'FormatterField',
    'FormatterMapping',
    'OCCompany',
    'OCCompanyWebsite',
    'OCRecruitAnnouncement',
    'OCResource',
    'UserApplication',
]
