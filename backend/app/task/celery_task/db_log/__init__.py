#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 导入任务以确保被注册
from .tasks import delete_db_opera_log, delete_db_login_log

__all__ = ['delete_db_opera_log', 'delete_db_login_log']
