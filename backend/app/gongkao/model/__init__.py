#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.gongkao.model.dict_major import GkDictMajor
from backend.app.gongkao.model.dict_region import GkDictRegion
from backend.app.gongkao.model.gangwei import GkGangwei
from backend.app.gongkao.model.hanyu import GkHanyu
from backend.app.gongkao.model.hanyu_checkin import GkHanyuCheckin
from backend.app.gongkao.model.hanyu_group import GkHanyuGroup, GkHanyuGroupItem
from backend.app.gongkao.model.hanyu_notebook import GkHanyuNotebook
from backend.app.gongkao.model.hanyu_review_log import GkHanyuReviewLog
from backend.app.gongkao.model.hanyu_user_book import GkHanyuUserBook
from backend.app.gongkao.model.hanyu_user_setting import GkHanyuUserSetting
from backend.app.gongkao.model.hanyu_user_word import GkHanyuUserWord
from backend.app.gongkao.model.hanyu_wordbook import GkHanyuWordbook
from backend.app.gongkao.model.hanyu_wordbook_entry import GkHanyuWordbookEntry
from backend.app.gongkao.model.practice_log import GongkaoPracticeLog, GongkaoPracticeModule
from backend.app.gongkao.model.user_profile import GkUserProfile

__all__ = [
    # 字典表
    'GkDictRegion',
    'GkDictMajor',
    'GkUserProfile',
    # 业务表
    'GkGangwei',
    'GkHanyu',
    'GkHanyuNotebook',
    'GkHanyuGroup',
    'GkHanyuGroupItem',
    # 学习本
    'GkHanyuWordbook',
    'GkHanyuWordbookEntry',
    'GkHanyuUserBook',
    'GkHanyuUserWord',
    'GkHanyuUserSetting',
    'GkHanyuReviewLog',
    'GkHanyuCheckin',
    'GongkaoPracticeLog',
    'GongkaoPracticeModule',
]
