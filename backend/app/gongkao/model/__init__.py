#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.gongkao.model.category import GkCategory
from backend.app.gongkao.model.ciyu import GkCiyu
from backend.app.gongkao.model.content import GkContent
from backend.app.gongkao.model.dict_major import GkDictMajor
from backend.app.gongkao.model.dict_region import GkDictRegion
from backend.app.gongkao.model.gangwei import GkGangwei
from backend.app.gongkao.model.guanmei import GkGuanmei
from backend.app.gongkao.model.jingyan import GkJingyan

from backend.app.gongkao.model.shiping import GkShiping
from backend.app.gongkao.model.shizhen import GkShizhen
from backend.app.gongkao.model.user_profile import (
    GkUserCertificate,
    GkUserEducation,
    GkUserHonor,
    GkUserProfile,
    GkUserRegionPreference,
    GkUserWorkExperience,
)
from backend.app.gongkao.model.zhenti import GkMaterial, GkQuestion, GkQuestionAnswer, GkQuestionOption

__all__ = [
    # 字典表
    'GkDictRegion',
    'GkDictMajor',
    # 用户画像
    'GkUserProfile',
    'GkUserEducation',
    'GkUserRegionPreference',
    'GkUserCertificate',
    'GkUserWorkExperience',
    'GkUserHonor',
    # 业务表
    'GkCategory',
    'GkCiyu',
    'GkContent',
    'GkGangwei',
    'GkGuanmei',
    'GkJingyan',

    'GkShiping',
    'GkShizhen',
    'GkQuestion',
    'GkQuestionOption',
    'GkQuestionAnswer',
    'GkMaterial',
]

