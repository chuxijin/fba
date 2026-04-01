#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import re
from datetime import date, datetime, time
from typing import Any

import httpx
from sqlalchemy import text

from backend.app.gongkao.crud.crud_content import content_dao
from backend.app.gongkao.schema.content import CreateContentParam, UpdateContentParam
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)

NEWS_API_URL = 'https://saduck.top/api/news/getNewsList'
NEWS_API_TIMEOUT = 30
SYSTEM_USER_ID = 1
CONTENT_TYPE_SHIZHEN = 'shizhen'
DEFAULT_TAGS = ['\u65f6\u653f', '\u65b0\u95fb\u8054\u64ad']




def build_content_slug(daily_date: date) -> str:
    """
    Build content slug.

    :param daily_date: News date
    :return:
    """
    return f'shizhen-{daily_date.isoformat()}'


def normalize_news_html(intro: str) -> str:
    """
    Normalize source HTML.

    :param intro: Raw HTML
    :return:
    """
    html = str(intro or '').strip()
    if not html:
        return ''

    html = html.replace('\r\n', '').replace('\n', '').replace('\r', '')
    html = re.sub(r'<mark[^>]*>(.*?)</mark>', r'\1', html, flags=re.IGNORECASE | re.DOTALL)
    html = html.replace('<spanstyle=', '<span style=')
    html = re.sub(r'</spanstyle="[^"]*">', '</span>', html)
    html = re.sub(r'<p[^>]*>', '<p style="text-align: justify;">', html, flags=re.IGNORECASE)
    return html


def strip_html_tags(content: str) -> str:
    """
    Strip HTML tags into plain text.

    :param content: HTML content
    :return:
    """
    text = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def build_summary(intro: str) -> str:
    """
    Build summary from all li items.

    :param intro: Source HTML
    :return:
    """
    items = re.findall(r'<li[^>]*>(.*?)</li>', intro, flags=re.IGNORECASE | re.DOTALL)
    cleaned_items: list[str] = []

    for item in items:
        text = strip_html_tags(item)
        if text:
            cleaned_items.append(text)

    if cleaned_items:
        summary = '\uFF1B'.join(cleaned_items)
    else:
        summary = strip_html_tags(intro)

    if len(summary) > 500:
        summary = f'{summary[:497].rstrip()}...'
    return summary


def build_extra(record: dict[str, Any], daily_date: date) -> dict[str, Any]:
    """
    Build lightweight extra payload.

    :param record: Remote record
    :param daily_date: News date
    :return:
    """
    extra: dict[str, Any] = {
        'content_type': CONTENT_TYPE_SHIZHEN,
        'daily_date': daily_date.isoformat(),
    }

    origin_url = str(record.get('url') or '').strip()
    if origin_url:
        extra['origin_url'] = origin_url

    return extra


async def fetch_news_list(page_num: int = 1, page_size: int = 10) -> dict[str, Any] | None:
    """
    Fetch remote news list.

    :param page_num: Page number
    :param page_size: Page size
    :return:
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
                headers={'Content-Type': 'application/json'},
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        logger.error('Fetch news list timed out: %s', NEWS_API_URL)
        return None
    except httpx.HTTPStatusError as exc:
        logger.error('Fetch news list failed with status: %s', exc.response.status_code)
        return None
    except Exception as exc:
        logger.error('Fetch news list failed: %s', exc)
        return None


@celery_app.task(name='sync_daily_news_to_shizhen', bind=True)
async def sync_daily_news_to_shizhen(self) -> dict[str, Any]:
    """同步每日新闻到时政内容"""
    result: dict[str, Any] = {
        'success': True,
        'fetched_count': 0,
        'created_count': 0,
        'updated_count': 0,
        'skipped_count': 0,
        'error_count': 0,
        'message': '',
    }

    api_response = await fetch_news_list(page_num=1, page_size=10)
    if not api_response:
        raise RuntimeError(f'获取新闻列表失败: {NEWS_API_URL}')

    if api_response.get('code') != 0:
        raise RuntimeError(f"API 返回错误: {api_response.get('message', 'unknown error')}")

    records = api_response.get('result', {}).get('records', [])
    result['fetched_count'] = len(records)

    if not records:
        result['message'] = 'API 返回成功但无记录'
        await self.on_warning(result['message'])
        return result

    async with async_db_session.begin() as db:
        for record in records:
            try:
                if int(record.get('isDelete') or 0) == 1:
                    result['skipped_count'] += 1
                    continue

                add_time = str(record.get('addTime') or '').strip()
                if not add_time:
                    result['error_count'] += 1
                    logger.warning('Missing addTime in record: %s', record.get('title'))
                    continue

                try:
                    daily_date = datetime.strptime(add_time, '%Y-%m-%d').date()
                except ValueError:
                    result['error_count'] += 1
                    logger.warning('Invalid addTime format: %s', add_time)
                    continue

                slug = build_content_slug(daily_date)
                title = str(record.get('title') or f'news {daily_date.isoformat()}').strip()
                content_html = normalize_news_html(str(record.get('intro') or ''))
                summary = build_summary(content_html)
                publish_time = datetime.combine(daily_date, time.min)
                extra = build_extra(record, daily_date)
                existing = await content_dao.get_by_slug(db, slug)

                if not existing:
                    create_obj = CreateContentParam(
                        title=title,
                        slug=slug,
                        content_html=content_html,
                        summary=summary,
                        tags=list(DEFAULT_TAGS),
                        is_pinned=False,
                        is_public=True,
                        is_published=True,
                        publish_time=publish_time,
                        extra=extra,
                    )
                    await content_dao.create(db, create_obj, created_by=SYSTEM_USER_ID)
                    result['created_count'] += 1
                    continue

                update_obj = UpdateContentParam()
                changed = False

                if existing.title != title:
                    update_obj.title = title
                    changed = True
                if existing.content_html != content_html:
                    update_obj.content_html = content_html
                    changed = True
                if existing.summary != summary:
                    update_obj.summary = summary
                    changed = True
                if existing.tags != DEFAULT_TAGS:
                    update_obj.tags = list(DEFAULT_TAGS)
                    changed = True
                if existing.is_public is not True:
                    update_obj.is_public = True
                    changed = True
                if existing.is_published is not True:
                    update_obj.is_published = True
                    changed = True

                existing_publish_date = existing.publish_time.date() if existing.publish_time else None
                if existing_publish_date != daily_date:
                    update_obj.publish_time = publish_time
                    changed = True
                if existing.extra != extra:
                    update_obj.extra = extra
                    changed = True

                if not changed:
                    result['skipped_count'] += 1
                    continue

                await content_dao.update(db, existing.id, update_obj, updated_by=SYSTEM_USER_ID)
                result['updated_count'] += 1
            except Exception as exc:
                result['error_count'] += 1
                logger.error('Failed to process news record: %s', exc)

    result['message'] = (
        f"sync done: fetched {result['fetched_count']}, "
        f"created {result['created_count']}, "
        f"updated {result['updated_count']}, "
        f"skipped {result['skipped_count']}, "
        f"errors {result['error_count']}"
    )
    logger.info(result['message'])

    if result['error_count'] > 0:
        await self.on_warning(result['message'])

    return result


@celery_app.task(name='update_hanyu_frequency')
async def update_hanyu_frequency() -> dict[str, Any]:
    """更新汉语词汇使用频次，统计成语在言语理解与表达题目的选项内容中出现的次数"""
    result: dict[str, Any] = {
        'success': True,
        'total_count': 0,
        'updated_count': 0,
        'error_count': 0,
        'elapsed_seconds': 0,
        'message': '',
    }

    start_time = datetime.now()
    logger.info('开始统计汉语词汇使用频次（仅言语理解与表达题目）...')

    async with async_db_session.begin() as db:
        # 第一步：统计目标选项数量
        logger.info('步骤 1/3: 筛选言语理解与表达题目的选项...')
        count_options_sql = text("""
            SELECT COUNT(DISTINCT oc.id)
            FROM study_question q
            INNER JOIN study_question_option qo ON qo.question_id = q.id
            INNER JOIN study_option_content oc ON oc.id = qo.content_id
            WHERE q.knowledge_point @> '["言语理解与表达"]'::jsonb
        """)
        options_count_result = await db.execute(count_options_sql)
        target_options_count = options_count_result.scalar()
        logger.info(f'找到 {target_options_count} 个目标选项')

        # 第二步：执行频次统计
        logger.info('步骤 2/3: 统计成语在选项中的出现次数...')
        sql = text("""
            WITH target_options AS (
                SELECT DISTINCT oc.id, oc.content
                FROM study_question q
                INNER JOIN study_question_option qo ON qo.question_id = q.id
                INNER JOIN study_option_content oc ON oc.id = qo.content_id
                WHERE q.knowledge_point @> '["言语理解与表达"]'::jsonb
            ),
            idiom_counts AS (
                SELECT
                    h.id,
                    COUNT(DISTINCT o.id) as freq
                FROM gk_hanyu h
                LEFT JOIN target_options o ON o.content LIKE '%' || h.name || '%'
                WHERE h.type = '成语'
                GROUP BY h.id
            )
            UPDATE gk_hanyu
            SET frequency = idiom_counts.freq
            FROM idiom_counts
            WHERE gk_hanyu.id = idiom_counts.id
            RETURNING gk_hanyu.id
        """)

        result_proxy = await db.execute(sql)
        updated_rows = result_proxy.fetchall()
        result['updated_count'] = len(updated_rows)
        logger.info(f'已更新 {result["updated_count"]} 条成语记录')

        # 第三步：获取总数
        logger.info('步骤 3/3: 获取成语总数...')
        count_sql = text("SELECT COUNT(*) FROM gk_hanyu WHERE type = '成语'")
        count_result = await db.execute(count_sql)
        result['total_count'] = count_result.scalar()

        await db.commit()
        logger.info('数据库事务已提交')

    elapsed = (datetime.now() - start_time).total_seconds()
    result['elapsed_seconds'] = round(elapsed, 2)

    result['message'] = (
        f"频次统计完成（言语理解与表达）: 总计 {result['total_count']} 个成语, "
        f"更新 {result['updated_count']} 条记录, "
        f"耗时 {result['elapsed_seconds']} 秒"
    )
    logger.info(result['message'])

    return result

