#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公考相关定时任务
"""
import json
import logging
import re
from datetime import date, datetime
from typing import Any

import httpx
from celery import shared_task

from backend.app.gongkao.crud.crud_shizhen import shizhen_dao
from backend.app.gongkao.schema.shizhen import CreateShizhenParam
from backend.core.conf import settings
from backend.database.db import async_db_session
from backend.plugin.email.utils.send import send_email
from backend.utils.dynamic_config import load_task_config

logger = logging.getLogger(__name__)

# 外部新闻API配置
NEWS_API_URL = 'https://saduck.top/api/news/getNewsList'
NEWS_API_TIMEOUT = 30  # 请求超时时间（秒）


async def send_task_notification(db, subject: str, content: str) -> None:
    """
    发送任务通知邮件

    :param db: 数据库会话
    :param subject: 邮件主题
    :param content: 邮件内容
    :return:
    """
    try:
        await load_task_config(db)
        if not settings.TASK_NOTIFY_EMAIL:
            logger.debug('未配置任务通知邮箱，跳过邮件发送')
            return

        await send_email(
            db=db,
            recipients=settings.TASK_NOTIFY_EMAIL,
            subject=subject,
            content=content,
        )
        logger.info(f'任务通知邮件已发送到: {settings.TASK_NOTIFY_EMAIL}')
    except Exception as e:
        logger.error(f'发送任务通知邮件失败: {str(e)}')


def process_news_content(intro: str, daily_date: date) -> dict[str, str]:
    """
    处理新闻内容，生成 original 和 summary

    :param intro: API 返回的原始 HTML 内容
    :param daily_date: 新闻日期
    :return: {'original': str, 'summary': str}
    """
    if not intro:
        return {'original': '', 'summary': ''}

    # 处理 original：清理转义符，标准化 HTML 格式
    original = _process_original(intro)

    # 处理 summary：提取标题生成目录
    summary = _process_summary(intro, daily_date)

    return {'original': original, 'summary': summary}


def _process_original(intro: str) -> str:
    """
    处理原始内容为标准化 HTML

    :param intro: API 返回的原始 HTML
    :return: 标准化后的 HTML
    """
    # 去除转义换行符
    content = intro.replace('\\r\\n', '').replace('\\n', '').replace('\\r', '')

    # 去除 <mark> 标签，保留内容
    content = re.sub(r'<mark>(.*?)</mark>', r'\1', content)

    # 将 <p> 标签替换为带样式的版本
    content = re.sub(r'<p[^>]*>', '<p style="text-align: justify;">', content)

    return content


def _process_summary(intro: str, daily_date: date) -> str:
    """
    从新闻内容中提取标题生成摘要目录

    :param intro: API 返回的原始 HTML
    :param daily_date: 新闻日期
    :return: 摘要 HTML
    """
    # 提取所有标题（<strong>标签中的内容）
    titles = re.findall(r'<strong>(\d+\..*?)</strong>', intro)

    if not titles:
        return ''

    # 摘要样式模板
    line_style = 'style="line-height: 1;"'
    color_style = 'style="color: rgb(248, 136, 37);"'

    summary_lines = []
    current_news_index = 0  # 跟踪当前处理的新闻索引

    for title in titles:
        # 清理标题中的多余空白
        title = title.strip()

        # 检查是否是联播快讯（国内联播快讯 或 国际联播快讯）
        if '联播快讯' in title:
            # 添加主标题
            summary_lines.append(
                f'<p {line_style}><span {color_style}>{title}：</span></p>'
            )
            current_news_index = int(re.match(r'(\d+)', title).group(1))

            # 提取该联播快讯下的子标题
            sub_titles = _extract_sub_titles(intro, current_news_index)
            for idx, sub_title in enumerate(sub_titles, 1):
                summary_lines.append(
                    f'<p {line_style}><span {color_style}>（{idx}）{sub_title}；</span></p>'
                )
        else:
            # 普通新闻标题
            summary_lines.append(
                f'<p {line_style}><span {color_style}>{title}；</span></p>'
            )

    # 添加节目信息
    date_str = daily_date.strftime('%Y%m%d')
    summary_lines.append(
        f'<p {line_style}><span {color_style}>（《新闻联播》 {date_str} 19:00）</span></p>'
    )

    return ''.join(summary_lines)


def _extract_sub_titles(intro: str, news_index: int) -> list[str]:
    """
    提取联播快讯下的子标题（从 <mark> 标签中提取）

    :param intro: 原始 HTML 内容
    :param news_index: 联播快讯的编号（如 9 或 14）
    :return: 子标题列表
    """
    # 查找从当前联播快讯到下一个主新闻之间的内容
    # 使用更宽松的匹配模式
    pattern = rf'<strong>\s*{news_index}\s*[\.．].*?联播快讯.*?</strong>(.*?)(?=<strong>\s*\d+\s*[\.．]|$)'
    match = re.search(pattern, intro, re.DOTALL)

    if not match:
        # 备用模式：只查找联播快讯后的内容
        pattern2 = rf'{news_index}\s*[\.．].*?联播快讯.*?</strong>(.*?)(?=<strong>|$)'
        match = re.search(pattern2, intro, re.DOTALL)

    if not match:
        return []

    section = match.group(1) if match.lastindex else match.group(0)

    # 提取 <mark> 标签中的内容作为子标题
    sub_titles = re.findall(r'<mark[^>]*>(.*?)</mark>', section, re.DOTALL)

    # 清理子标题中的 HTML 标签和空白
    cleaned_titles = []
    for title in sub_titles:
        # 去除内部 HTML 标签
        clean = re.sub(r'<[^>]+>', '', title).strip()
        if clean:
            cleaned_titles.append(clean)

    # 如果没有 mark 标签，尝试从段落中提取标题
    if not cleaned_titles:
        # 查找紧跟在"央视网消息"段落后的短标题段落
        paragraphs = re.findall(r'<p[^>]*>([^<]*?)</p>', section)
        for p in paragraphs:
            text = p.strip()
            # 跳过空段落和包含"央视网消息"的段落
            if not text or '央视网消息' in text:
                continue
            # 短句作为子标题（通常是简短的新闻标题）
            if len(text) < 60 and not text.endswith('。'):
                cleaned_titles.append(text)

    return cleaned_titles


async def fetch_news_list(page_num: int = 1, page_size: int = 10) -> dict[str, Any] | None:
    """
    从外部API获取新闻列表

    :param page_num: 页码
    :param page_size: 每页数量
    :return: API响应数据
    """
    try:
        async with httpx.AsyncClient(timeout=NEWS_API_TIMEOUT) as client:
            response = await client.post(
                NEWS_API_URL,
                json={
                    'total': 0,
                    'pageSize': page_size,
                    'pageNum': page_num,
                },
                headers={
                    'Content-Type': 'application/json',
                }
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        logger.error(f'获取新闻列表超时: {NEWS_API_URL}')
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f'获取新闻列表HTTP错误: {e.response.status_code}')
        return None
    except Exception as e:
        logger.error(f'获取新闻列表异常: {str(e)}')
        return None


@shared_task(name='backend.app.task.tasks.gongkao.tasks.sync_daily_news_to_shizhen')
async def sync_daily_news_to_shizhen() -> dict[str, Any]:
    """
    每日定时获取新闻并同步到gk_shizhen表

    任务会获取最新的新闻列表，检查是否已存在相同日期的记录，
    如果不存在则创建新记录。

    :return: 同步结果统计
    """
    result = {
        'success': True,
        'fetched_count': 0,
        'created_count': 0,
        'skipped_count': 0,
        'error_count': 0,
        'message': '',
    }

    try:
        # 获取第一页新闻（通常只需要最新的几条）
        api_response = await fetch_news_list(page_num=1, page_size=5)

        if not api_response:
            result['success'] = False
            result['message'] = '获取新闻列表失败'
            # 发送通知邮件
            async with async_db_session.begin() as db:
                await send_task_notification(
                    db,
                    subject='【公考任务失败】获取新闻列表失败',
                    content=f'任务执行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n错误信息: 无法从外部 API 获取新闻列表，请检查 API 连接是否正常。\n\nAPI 地址: {NEWS_API_URL}',
                )
            return result

        # 检查API响应格式
        if api_response.get('code') != 0:
            result['success'] = False
            result['message'] = f"API返回错误: {api_response.get('message', '未知错误')}"
            # 发送通知邮件
            async with async_db_session.begin() as db:
                await send_task_notification(
                    db,
                    subject='【公考任务失败】API 返回错误',
                    content=f'任务执行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n错误信息: {result["message"]}\n\nAPI 响应: {json.dumps(api_response, ensure_ascii=False, indent=2)}',
                )
            return result

        records = api_response.get('result', {}).get('records', [])
        result['fetched_count'] = len(records)

        if not records:
            result['message'] = '没有获取到新闻记录'
            # 发送通知邮件
            async with async_db_session.begin() as db:
                await send_task_notification(
                    db,
                    subject='【公考任务警告】未获取到新闻记录',
                    content=f'任务执行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n警告信息: API 返回成功但没有新闻记录，可能是数据源暂无更新。',
                )
            return result

        async with async_db_session.begin() as db:
            for record in records:
                try:
                    # 直接使用 addTime 作为日期
                    add_time = record.get('addTime')
                    if not add_time:
                        logger.warning(f"新闻记录缺少 addTime: {record.get('title')}")
                        result['error_count'] += 1
                        continue
                        
                    try:
                        daily_date = datetime.strptime(add_time, '%Y-%m-%d').date()
                    except ValueError:
                        logger.warning(f"日期格式解析错误: {add_time}")
                        result['error_count'] += 1
                        continue

                    # 检查是否已存在该日期的记录
                    existing = await shizhen_dao.get_by_date(db, daily_date)
                    if existing:
                        logger.info(f"日期 {daily_date} 的时政记录已存在，跳过")
                        result['skipped_count'] += 1
                        continue

                    # 处理新闻内容（纯代码处理，不调用 AI）
                    intro = record.get('intro', '')
                    processed = process_news_content(intro, daily_date)

                    # 创建新记录
                    create_param = CreateShizhenParam(
                        daily_date=daily_date,
                        original=processed['original'],
                        summary=processed['summary'],
                    )

                    await shizhen_dao.create(db, create_param, created_by=1)  # 系统用户ID为1
                    result['created_count'] += 1
                    logger.info(f"成功创建日期 {daily_date} 的时政记录")

                except Exception as e:
                    logger.error(f"处理新闻记录时出错: {str(e)}")
                    result['error_count'] += 1

        result['message'] = (
            f"同步完成: 获取 {result['fetched_count']} 条, "
            f"新增 {result['created_count']} 条, "
            f"跳过 {result['skipped_count']} 条, "
            f"错误 {result['error_count']} 条"
        )
        logger.info(result['message'])

        # 如果有错误，发送汇总通知
        if result['error_count'] > 0:
            async with async_db_session.begin() as db:
                await send_task_notification(
                    db,
                    subject='【公考任务警告】任务完成但存在错误',
                    content=f'任务执行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n执行结果:\n{result["message"]}\n\n建议: 请查看日志了解具体错误原因。',
                )

    except Exception as e:
        result['success'] = False
        result['message'] = f'同步任务执行异常: {str(e)}'
        logger.error(result['message'])
        # 发送异常通知
        try:
            async with async_db_session.begin() as db:
                await send_task_notification(
                    db,
                    subject='【公考任务失败】任务执行异常',
                    content=f'任务执行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n异常信息: {result["message"]}\n\n请立即检查任务日志和系统状态。',
                )
        except Exception as notify_error:
            logger.error(f'发送异常通知邮件失败: {str(notify_error)}')

    return result
