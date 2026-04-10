#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import re
from datetime import date, datetime, time
from typing import Any

import httpx

from backend.app.content.crud.crud_content import content_dao
from backend.app.content.schema.content import CreateContentParam, UpdateContentParam
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)

NEWS_API_URL = 'https://saduck.top/api/news/getNewsList'
NEWS_API_TIMEOUT = 30
SYSTEM_USER_ID = 1
CONTENT_TYPE_SHIZHEN = 'shizhen'
DEFAULT_TAGS = ['时政', '新闻联播']
APP_CODE_GONGKAO = 'gongkao'


def build_content_slug(daily_date: date) -> str:
    return f'shizhen-{daily_date.isoformat()}'


def normalize_news_html(intro: str) -> str:
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
    text = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def build_summary(intro: str) -> str:
    items = re.findall(r'<li[^>]*>(.*?)</li>', intro, flags=re.IGNORECASE | re.DOTALL)
    cleaned_items: list[str] = []
    for item in items:
        text = strip_html_tags(item)
        if text:
            cleaned_items.append(text)
    if cleaned_items:
        summary = '；'.join(cleaned_items)
    else:
        summary = strip_html_tags(intro)
    if len(summary) > 500:
        summary = f'{summary[:497].rstrip()}...'
    return summary


def build_extra(record: dict[str, Any], daily_date: date) -> dict[str, Any]:
    extra: dict[str, Any] = {
        'content_type': CONTENT_TYPE_SHIZHEN,
        'daily_date': daily_date.isoformat(),
    }
    origin_url = str(record.get('url') or '').strip()
    if origin_url:
        extra['origin_url'] = origin_url
    return extra


async def fetch_news_list(page_num: int = 1, page_size: int = 10) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=NEWS_API_TIMEOUT) as client:
            response = await client.post(
                NEWS_API_URL,
                json={'total': 0, 'pageSize': page_size, 'pageNum': page_num},
                headers={'Content-Type': 'application/json'},
            )
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        logger.error('Fetch news list failed: %s', exc)
        return None


@celery_app.task(name='sync_daily_news_to_shizhen', bind=True)
async def sync_daily_news_to_shizhen(self) -> dict[str, Any]:
    result: dict[str, Any] = {
        'success': True, 'fetched_count': 0, 'created_count': 0, 'updated_count': 0,
        'skipped_count': 0, 'error_count': 0, 'message': '',
    }
    api_response = await fetch_news_list(page_num=1, page_size=10)
    if not api_response or api_response.get('code') != 0:
        raise RuntimeError('获取新闻列表失败')
    records = api_response.get('result', {}).get('records', [])
    result['fetched_count'] = len(records)
    async with async_db_session.begin() as db:
        for record in records:
            try:
                if int(record.get('isDelete') or 0) == 1:
                    result['skipped_count'] += 1
                    continue
                add_time = str(record.get('addTime') or '').strip()
                daily_date = datetime.strptime(add_time, '%Y-%m-%d').date()
                slug = build_content_slug(daily_date)
                title = str(record.get('title') or f'news {daily_date.isoformat()}').strip()
                content_html = normalize_news_html(str(record.get('intro') or ''))
                summary = build_summary(content_html)
                publish_time = datetime.combine(daily_date, time.min)
                extra = build_extra(record, daily_date)
                
                # 使用通用的 content_dao 查询，并指定 app_code
                existing = await content_dao.get_by_slug(db, slug)

                if not existing:
                    create_obj = CreateContentParam(
                        app_code=APP_CODE_GONGKAO, # 必填字段
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
                    await content_dao.create(db, create_obj)
                    result['created_count'] += 1
                    continue

                update_obj = UpdateContentParam()
                changed = False
                if existing.title != title: update_obj.title = title; changed = True
                if existing.content_html != content_html: update_obj.content_html = content_html; changed = True
                if existing.summary != summary: update_obj.summary = summary; changed = True
                if existing.extra != extra: update_obj.extra = extra; changed = True

                if changed:
                    await content_dao.update(db, existing.id, update_obj)
                    result['updated_count'] += 1
                else:
                    result['skipped_count'] += 1
            except Exception as exc:
                result['error_count'] += 1
                logger.error('Failed to process news record: %s', exc)
    return result
