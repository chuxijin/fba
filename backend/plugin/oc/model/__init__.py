# oc models
from backend.plugin.oc.model.campus_recruit import CampusRecruit
from backend.plugin.oc.model.intern_recruit import InternRecruit
from backend.plugin.oc.model.resource import OCResource
from backend.plugin.oc.model.user_application import UserApplication
from backend.plugin.oc.model.formatter import FormatterField, FormatterEmbedding, FormatterMapping

__all__ = [
    'CampusRecruit',
    'InternRecruit',
    'OCResource',
    'UserApplication',
    'FormatterField',
    'FormatterEmbedding',
    'FormatterMapping',
]
