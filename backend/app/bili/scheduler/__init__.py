#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""任务调度器初始化"""
from backend.app.bili.scheduler.jobs.send_to_others_comment_job import send_to_others_comment_task
from backend.app.bili.scheduler.manager import task_scheduler


def register_all_tasks():
    """注册所有任务类型"""
    # 场景C：监控指定作品评论 + 发私信
    task_scheduler.register_task('send_to_others_comment', send_to_others_comment_task)

    # TODO: 场景A和场景B后续添加
    # task_scheduler.register_task('reply_my_message', reply_my_message_task)
    # task_scheduler.register_task('reply_my_comment', reply_my_comment_task)
