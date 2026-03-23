#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.gongkao.model.category import GkCategory
from backend.app.gongkao.model.content import GkContent
from backend.app.gongkao.model.dict_major import GkDictMajor
from backend.app.gongkao.model.dict_region import GkDictRegion
from backend.app.gongkao.model.gangwei import GkGangwei
from backend.app.gongkao.model.hanyu import GkHanyu
from backend.app.gongkao.model.user_profile import GkUserProfile
from backend.app.gongkao.model.zhenti import GkMaterial, GkQuestion, GkQuestionAnswer, GkQuestionOption

__all__ = [
    # 字典表
    'GkDictRegion',
    'GkDictMajor',
    # 用户画像
    'GkUserProfile',
    # 业务表
    'GkCategory',
    'GkContent',
    'GkGangwei',
    'GkHanyu',
    'GkQuestion',
    'GkQuestionOption',
    'GkQuestionAnswer',
    'GkMaterial',
]
