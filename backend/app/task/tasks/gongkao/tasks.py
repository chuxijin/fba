#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公考相关定时任务
"""
import json
import logging
from datetime import date, datetime
from typing import Any

import httpx
from celery import shared_task

from backend.app.gongkao.crud.crud_shizhen import shizhen_dao
from backend.app.gongkao.schema.shizhen import CreateShizhenParam
from backend.core.conf import settings
from backend.database.db import async_db_session
from backend.plugin.ai.crud.crud_model import ai_model_dao
from backend.plugin.ai.schema.chat import AIChat
from backend.plugin.ai.service.chat_service import ai_chat_service
from backend.plugin.email.utils.send import send_email
from backend.utils.dynamic_config import load_task_config

logger = logging.getLogger(__name__)

# 外部新闻API配置
NEWS_API_URL = 'https://saduck.top/api/news/getNewsList'
NEWS_API_TIMEOUT = 30  # 请求超时时间（秒）
AI_MODEL_NAME = 'gpt-4o'


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


async def process_content_with_ai(db, intro: str) -> dict[str, str]:
    """
    使用 AI 规整内容并提取摘要

    :param db: 数据库会话
    :param intro: 原始内容
    :return: {'original': str, 'summary': str}
    """
    if not intro:
        return {'original': '', 'summary': ''}

    # 查找模型
    models = await ai_model_dao.select_models(db, model_id=AI_MODEL_NAME)
    if not models:
        logger.error(f'未找到 AI 模型: {AI_MODEL_NAME}')
        # 发送通知邮件（AI 模型配置问题）
        await send_task_notification(
            db,
            subject='【公考任务警告】AI 模型未找到',
            content=f'任务执行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n警告信息: 未找到配置的 AI 模型 "{AI_MODEL_NAME}"，请检查 AI 模型配置。\n\n降级处理: 使用原始内容，摘要截取前 100 字符。',
        )
        # AI 不可用时，直接返回原内容，摘要为空或截取
        return {'original': intro, 'summary': intro[:100]}
    
    model_conf = models[0]

    prompt = f"""
你是一个专业的新闻编辑。请将以下 HTML 格式的新闻内容进行规整，并提取核心摘要。
要求：
1. 'original' 字段：保留重要信息（包括 <mark> 标签中的重点），去除无用的 HTML 标签样式，整理为易读的文本或精简 HTML。
2. 'summary' 字段：提取不超过 300 字的核心摘要。
3. 请严格返回合法的 JSON 格式，不要包含 Markdown 代码块标记（如 ```json）。

内容如下：
{intro}
"""

    try:
        chat_param = AIChat(
            provider_id=model_conf.provider_id,
            model_id=AI_MODEL_NAME,
            user_prompt=prompt,
            temperature=0.3, # 降低随机性
            parallel_tool_calls=None, # 部分模型/渠道不支持此参数
        )
        
        response_text = await ai_chat_service.invoke(db=db, chat=chat_param)
        
        # 清理可能存在的代码块标记
        cleaned_text = response_text.replace('```json', '').replace('```', '').strip()
        
        result = json.loads(cleaned_text)
        return {
            'original': result.get('original', intro),
            'summary': result.get('summary', ''),
        }
    except Exception as e:
        logger.error(f'AI 处理内容失败: {str(e)}')
        # 降级处理
        return {'original': intro, 'summary': intro[:100]}


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


@shared_task(name='sync_daily_news_to_shizhen')
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

                    # 使用 AI 处理内容
                    intro = record.get('intro', '')
                    ai_result = await process_content_with_ai(db, intro)

                    # 创建新记录
                    create_param = CreateShizhenParam(
                        daily_date=daily_date,
                        original=ai_result['original'],
                        summary=ai_result['summary'],
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
