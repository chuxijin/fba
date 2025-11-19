#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量私信任务"""
from backend.common.log import log


async def batch_sender_task(config: dict):
    """
    批量私信任务（对应你粘贴的脚本功能）

    :param config: 任务配置
    """
    log.info(f'📤 开始批量发送私信，配置: {config}')

    # TODO: 实现实际的批量私信逻辑
    # 1. 从 config 获取筛选条件（等级、注册时间）
    # 2. 爬取评论用户列表
    # 3. 过滤黑名单、去重（bili_duplicate_check）
    # 4. 从 bili_template 获取话术
    # 5. 添加随机后缀（emoji/数字/空格）
    # 6. 随机间隔发送（bili_interval_min/max）
    # 7. 记录发送结果（SUCCESS/FAIL/FATAL）

    work_id = config.get('work_id')
    template_id = config.get('template_id')

    log.info(f'作品 ID: {work_id}, 话术模板 ID: {template_id}')

    # 这里后续会调用 bilibili-api-python
    # from bilibili_api import comment, user
    # comments = await comment.get_comments(...)
    # for c in comments:
    #     u = user.User(c['mid'])
    #     await u.send_msg(message)

    log.success('✅ 批量私信任务完成')
