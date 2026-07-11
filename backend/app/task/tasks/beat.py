#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from backend.app.task.utils.tzcrontab import TzAwareCrontab


def get_local_beat_schedule() -> dict[str, dict[str, Any]]:
    """获取本地 Celery beat 任务配置"""
    return {
        '清理操作日志': {
            'task': 'delete_db_opera_log',
            'schedule': TzAwareCrontab('0', '0', day_of_week='6'),
        },
        '清理登录日志': {
            'task': 'delete_db_login_log',
            'schedule': TzAwareCrontab('0', '0', day_of_month='15'),
        },
        '清理 Celery 任务结果': {
            'task': 'delete_celery_task_results',
            'schedule': TzAwareCrontab('0', '3'),
        },
        '文件同步定时任务检查': {
            'task': 'check_and_execute_filesync_cron_tasks',
            'schedule': TzAwareCrontab('*/5'),
        },
        '刷新网盘用户信息': {
            'task': 'refresh_all_valid_drive_users',
            'schedule': TzAwareCrontab('0', '22'),
        },
        '检查并刷新过期资源': {
            'task': 'check_and_refresh_expiring_resources',
            'schedule': TzAwareCrontab('0', '23'),
        },
        '清理本地失效分享': {
            'task': 'cleanup_expired_local_shares',
            'schedule': TzAwareCrontab('0', '5'),
        },
        '刷新更新模式资源': {
            'task': 'refresh_resources_with_update_mode',
            'schedule': TzAwareCrontab('0', '7'),
        },
        '清理过期文件同步数据': {
            'task': 'delete_filesync_data_older_than_30_days',
            'schedule': TzAwareCrontab('0', '2'),
        },
        '更新用户每日排名': {
            'task': 'update_daily_user_ranks',
            'schedule': TzAwareCrontab('5', '0'),
        },
        '同步每日时政新闻': {
            'task': 'sync_daily_news_to_shizhen',
            'schedule': TzAwareCrontab('0', '22'),
        },
        '检查过期用户角色': {
            'task': 'check_expired_user_roles',
            'schedule': TzAwareCrontab('30'),
        },
        '检查过期订阅': {
            'task': 'check_expired_memberships',
            'schedule': TzAwareCrontab('10', '0'),
        },
        '关闭超时支付订单': {
            'task': 'close_timeout_pending_pay_orders',
            'schedule': TzAwareCrontab('*/5'),
        },
        '同步资源热度评分': {
            'task': 'sync_resource_hot_scores',
            'schedule': TzAwareCrontab('0', '1'),
        },
        '排行榜机器人模拟': {
            'task': 'simulate_bot_activity',
            'schedule': TzAwareCrontab('0', '*/2'),
        },
        '释放过期悬赏领取': {
            'task': 'release_expired_quest_claims',
            'schedule': TzAwareCrontab('*/5'),
        },
        '清理过期题本': {
            'task': 'cleanup_expired_render_books',
            'schedule': TzAwareCrontab('0', '4'),
        },
        'OC 爬取校招岗位数据': {
            'task': 'crawl_jobs_task',
            'schedule': TzAwareCrontab('0', '*/6'),
            'args': ['campus'],
        },
        '学习规划过期项清理': {
            'task': 'sweep_expired_study_plan_items',
            'schedule': TzAwareCrontab('30', '0'),
        },
    }
