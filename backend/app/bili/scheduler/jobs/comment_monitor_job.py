#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评论监控任务"""
import json

from bilibili_api import Credential, comment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.bili.model.account import BiliAccount
from backend.app.bili.model.task_config import BiliTaskConfig
from backend.app.bili.model.template import BiliTemplate
from backend.app.bili.model.work import BiliWork
from backend.common.log import log
from backend.database.db import async_engine


async def comment_monitor_task(task_config: BiliTaskConfig) -> int:
    """
    评论监控任务 - 查看指定作品的评论并根据条件自动回复

    :param task_config: 任务配置
    :return: 回复成功数量
    """
    reply_count = 0

    async with AsyncSession(async_engine) as db:
        # 获取关联作品
        if not task_config.work_id:
            log.warning('⚠️ 评论监控任务未配置作品 ID')
            return 0

        stmt = select(BiliWork).where(BiliWork.id == task_config.work_id)
        result = await db.execute(stmt)
        work = result.scalar_one_or_none()

        if not work:
            log.warning(f'⚠️ 作品 ID {task_config.work_id} 不存在')
            return 0

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

        # 获取模板（评论类型）
        template_ids = json.loads(task_config.template_ids) if task_config.template_ids else []
        templates = []
        if template_ids:
            stmt = select(BiliTemplate).where(
                BiliTemplate.id.in_(template_ids), BiliTemplate.status == 1, BiliTemplate.template_type == 'comment'
            )
            result = await db.execute(stmt)
            templates = result.scalars().all()

        if not templates:
            log.warning('⚠️ 没有可用的评论模板')
            return 0

        # 使用第一个账号获取评论
        account = accounts[0]

        try:
            # 解析 Cookie
            cookie_dict = _parse_cookie(account.cookie)
            credential = Credential(
                sessdata=cookie_dict.get('SESSDATA'),
                bili_jct=cookie_dict.get('bili_jct'),
                buvid3=cookie_dict.get('buvid3'),
            )

            # 获取视频评论
            comments_data = await comment.get_comments(
                oid=work.aid,
                type_=comment.CommentResourceType.VIDEO,
                credential=credential,
            )

            log.info(f'📥 作品 {work.title} 获取评论成功，共 {len(comments_data.get("replies", []))} 条')

            # TODO: 实现评论回复逻辑
            # 1. 遍历新评论
            # 2. 检查去重（bili_duplicate_check）
            # 3. 筛选用户（等级、注册时间）
            # 4. 选择模板并回复
            # 5. 记录操作

        except Exception as e:
            log.error(f'❌ 获取评论失败: {str(e)}')

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
