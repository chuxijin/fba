#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 为了避免循环导入，这里不进行直接导入
# 需要使用这些模型时，请直接从对应模块导入

# 导入所有模型以确保它们被注册到 SQLAlchemy 注册表中
from .filesync import SyncConfig, SyncTask, SyncTaskItem
from .resource import Resource, ResourceViewHistory
from .rule_template import RuleTemplate
from .user import DriveAccount

# 注意：Category 已迁移到 backend.app.admin.model.category
# 使用时请导入：from backend.app.admin.model.category import Category

__all__ = [
    'DriveAccount',
    'SyncConfig',
    'SyncTask',
    'SyncTaskItem',
    'RuleTemplate',
    'Resource',
    'ResourceViewHistory',
]
