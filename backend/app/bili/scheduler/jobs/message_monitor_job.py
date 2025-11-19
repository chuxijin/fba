#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""私信监控任务"""
import json
import random

from bilibili_api import Credential, user
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.bili.model.account import BiliAccount
from backend.app.bili.model.duplicate_check import BiliDuplicateCheck
from backend.app.bili.model.task_config import BiliTaskConfig
from backend.app.bili.model.template import BiliTemplate
from backend.common.log import log
from backend.database.db import async_engine


async def message_monitor_task(task_config: BiliTaskConfig) -> int:
    """
    私信监控任务 - 查看私信列表并根据条件自动回复

    :param task_config: 任务配置
    :return: 回复成功数量
    """
    reply_count = 0

    async with AsyncSession(async_engine) as db:
        # 获取账号
        if task_config.account_id:
            stmt = select(BiliAccount).where(BiliAccount.id == task_config.account_id, BiliAccount.status == 1)
        else:
            stmt = select(BiliAccount).where(BiliAccount.status == 1)

        result = await db.execute(stmt)
        accounts = result.scalars().all()

        if not accounts:
            log.warning('⚠️ 没有可用账号')
            return 0

        # 获取模板
        template_ids = json.loads(task_config.template_ids) if task_config.template_ids else []
        templates = []
        if template_ids:
            stmt = select(BiliTemplate).where(
                BiliTemplate.id.in_(template_ids), BiliTemplate.status == 1, BiliTemplate.template_type == 'message'
            )
            result = await db.execute(stmt)
            templates = result.scalars().all()

        if not templates:
            log.warning('⚠️ 没有可用的私信模板')
            return 0

        # 解析筛选条件
        filter_config = json.loads(task_config.filter_config) if task_config.filter_config else {}
        exclude_levels = filter_config.get('exclude_levels', [])
        exclude_months = filter_config.get('exclude_months', 0)

        # 遍历账号
        for account in accounts:
            try:
                # 解析 Cookie
                cookie_dict = _parse_cookie(account.cookie)
                credential = Credential(
                    sessdata=cookie_dict.get('SESSDATA'),
                    bili_jct=cookie_dict.get('bili_jct'),
                    buvid3=cookie_dict.get('buvid3'),
                )

                # 获取私信列表
                u = user.User(int(account.mid), credential=credential)
                # TODO: 这里需要使用 bilibili-api 的私信接口
                # messages = await u.get_messages()  # 示例，实际接口可能不同

                log.info(f'📥 账号 {account.account_name} 获取私信成功')

                # TODO: 实现私信回复逻辑
                # 1. 遍历新私信
                # 2. 检查去重（bili_duplicate_check）
                # 3. 筛选用户（等级、注册时间）
                # 4. 选择模板并回复
                # 5. 记录操作

            except Exception as e:
                log.error(f'❌ 账号 {account.account_name} 处理失败: {str(e)}')

    return reply_count


def _parse_cookie(cookie_str: str) -> dict:
    """
    解析 Cookie 字符串

    :param cookie_str: Cookie 字符串
    :return:
    """
    cookie_dict = {}
    if not cookie_str:
        return cookie_dict

    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookie_dict[key.strip()] = value.strip()

    return cookie_dict
