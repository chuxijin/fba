#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from celery.schedules import schedule

from backend.app.task.utils.tzcrontab import TzAwareCrontab

LOCAL_BEAT_SCHEDULE = {
    'task_demo_sync': {
        'task': 'task_demo',
        'schedule': schedule(30),
    },
    'task_demo_async': {
        'task': 'task_demo_async',
        'schedule': TzAwareCrontab('1'),
    },
    'task_demo_params': {
        'task': 'task_demo_params',
        'schedule': TzAwareCrontab('1'),
        'args': ['你好，'],
        'kwargs': {'world': '世界'},
    },
    'delete_db_opera_log': {
        'task': 'delete_db_opera_log',
        'schedule': TzAwareCrontab('0', '0', day_of_week='6'),
    },
    'delete_db_login_log': {
        'task': 'delete_db_login_log',
        'schedule': TzAwareCrontab('0', '0', day_of_month='15'),
    },
    'delete_celery_task_results': {
        'task': 'delete_celery_task_results',
        'schedule': TzAwareCrontab('0', '3'),
    },
    'check_filesync_cron_tasks': {
        'task': 'check_and_execute_filesync_cron_tasks',
        'schedule': TzAwareCrontab('*/5'),
    },
    'refresh_all_valid_drive_users': {
        'task': 'refresh_all_valid_drive_users',
        'schedule': TzAwareCrontab('0', '22'),
    },
    'check_and_refresh_expiring_resources': {
        'task': 'check_and_refresh_expiring_resources',
        'schedule': TzAwareCrontab('0', '23'),
    },
    'cleanup_expired_local_shares': {
        'task': 'cleanup_expired_local_shares',
        'schedule': TzAwareCrontab('0', '5'),
    },
    'refresh_resources_with_update_mode': {
        'task': 'refresh_resources_with_update_mode',
        'schedule': TzAwareCrontab('0', '7'),
    },
    'delete_filesync_data_older_than_30_days': {
        'task': 'delete_filesync_data_older_than_30_days',
        'schedule': TzAwareCrontab('0', '2'),
    },
    'update_daily_user_ranks': {
        'task': 'update_daily_user_ranks',
        'schedule': TzAwareCrontab('5', '0'),
    },
    'sync_daily_news_to_shizhen': {
        'task': 'sync_daily_news_to_shizhen',
        'schedule': TzAwareCrontab('0', '8'),
    },
    'update_jia_item_status': {
        'task': 'update_jia_item_status',
        'schedule': TzAwareCrontab('0'),
    },
    'check_expired_user_roles': {
        'task': 'check_expired_user_roles',
        'schedule': TzAwareCrontab('30'),
    },
    'check_expired_memberships': {
        'task': 'check_expired_memberships',
        'schedule': TzAwareCrontab('35'),
    },
    'sync_resource_hot_scores': {
        'task': 'sync_resource_hot_scores',
        'schedule': TzAwareCrontab('0', '1'),
    },
}
