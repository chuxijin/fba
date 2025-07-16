#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from celery.schedules import schedule

from backend.app.task.utils.tzcrontab import TzAwareCrontab

LOCAL_BEAT_SCHEDULE = {
    '测试同步任务': {
        'task': 'task_demo',
        'schedule': schedule(5),
    },
    '测试异步任务': {
        'task': 'task_demo_async',
        'schedule': TzAwareCrontab('1'),
    },
    '清理操作日志': {
        'task': 'backend.app.task.tasks.db_log.tasks.delete_db_opera_log',
        'schedule': TzAwareCrontab('0', '0', day_of_week='6'),
    },
    '清理登录日志': {
        'task': 'backend.app.task.tasks.db_log.tasks.delete_db_login_log',
        'schedule': TzAwareCrontab('0', '0', day_of_month='15'),
    },
    # 文件同步定时任务检查 - 每5分钟执行一次
    '文件同步定时任务检查': {
        'task': 'check_and_execute_filesync_cron_tasks',
        'schedule': TzAwareCrontab('*/5'),  # 每5分钟
    },
    # 刷新网盘用户信息 - 每天晚上10点执行
    '刷新网盘用户信息': {
        'task': 'refresh_all_valid_drive_users',
        'schedule': TzAwareCrontab('0', '22'),  # 每天晚上10点
    },
    # 检查并刷新过期资源 - 每天晚上11点执行
    '检查并刷新过期资源': {
        'task': 'check_and_refresh_expiring_resources',
        'schedule': TzAwareCrontab('0', '23'),  # 每天晚上11点
    },
    # 清理本地失效分享 - 每天凌晨5点执行
    '清理本地失效分享': {
        'task': 'cleanup_expired_local_shares',
        'schedule': TzAwareCrontab('0', '5'),  # 每天凌晨5点
    },
}
