#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from backend.app.task.utils.tzcrontab import TzAwareCrontab


def get_local_beat_schedule() -> dict[str, dict[str, Any]]:
    """获取本地 Celery beat 任务配置"""
    return {
        '清理操作日志': {
            'task': 'db_log:delete_db_opera_log',
            'schedule': TzAwareCrontab('0', '0', day_of_week='6'),
        },
        '清理登录日志': {
            'task': 'db_log:delete_db_login_log',
            'schedule': TzAwareCrontab('0', '0', day_of_month='15'),
        },
        '清理 Celery 任务结果': {
            'task': 'db_log:delete_celery_task_results',
            'schedule': TzAwareCrontab('0', '3'),
        },
        'MyDrive 定时同步任务检查': {
            'task': 'mydrive:check_and_execute_cron_tasks',
            'schedule': TzAwareCrontab('*/5'),
        },
        '刷新 MyDrive 网盘账户资料': {
            'task': 'mydrive:sync_active_account_profiles',
            'schedule': TzAwareCrontab('0', '22'),
        },
        '清理 MyDrive 本地过期分享': {
            'task': 'mydrive:cleanup_expired_local_shares',
            'schedule': TzAwareCrontab('15', '5'),
        },
        '处理 MyDrive 到期资源策略': {
            'task': 'mydrive:process_expired_resource_policies',
            'schedule': TzAwareCrontab('30', '7'),
        },
        '刷新 MyDrive 定时更新资源': {
            'task': 'mydrive:refresh_scheduled_resource_shares',
            'schedule': TzAwareCrontab('45', '7'),
        },
        '清理过期文件同步数据': {
            'task': 'db_log:delete_filesync_data_older_than_30_days',
            'schedule': TzAwareCrontab('0', '2'),
        },
        '更新用户每日排名': {
            'task': 'qbank:update_daily_user_ranks',
            'schedule': TzAwareCrontab('5', '0'),
        },
        '同步每日时政新闻': {
            'task': 'gongkao:sync_daily_news_to_shizhen',
            'schedule': TzAwareCrontab('0', '22'),
        },
        '检查过期用户角色': {
            'task': 'user:check_expired_user_roles',
            'schedule': TzAwareCrontab('30'),
        },
        '检查过期订阅': {
            'task': 'user:check_expired_memberships',
            'schedule': TzAwareCrontab('10', '0'),
        },
        '关闭超时支付订单': {
            'task': 'payment:close_timeout_pending_pay_orders',
            'schedule': TzAwareCrontab('*/5'),
        },
        '释放过期悬赏领取': {
            'task': 'quest:release_expired_quest_claims',
            'schedule': TzAwareCrontab('*/5'),
        },
        '清理过期题本': {
            'task': 'render_book:cleanup_expired_render_books',
            'schedule': TzAwareCrontab('0', '4'),
        },
        'OC 爬取校招岗位数据': {
            'task': 'oc:crawl_jobs_task',
            'schedule': TzAwareCrontab('0', '*/6'),
            'args': ['campus'],
        },
        '学习规划过期项清理': {
            'task': 'study_plan:sweep_expired_study_plan_items',
            'schedule': TzAwareCrontab('30', '0'),
        },
    }
