#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import re

from collections import deque
from datetime import date, datetime, time
from typing import Any

import httpx

from sqlalchemy import text

from backend.app.content.crud.crud_content import content_dao
from backend.app.content.schema.content import CreateContentParam, UpdateContentParam
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)

NEWS_API_URL = 'https://saduck.top/api/news/getNewsList'
NEWS_API_TIMEOUT = 30
SYSTEM_USER_ID = 1
CONTENT_TYPE_SHIZHEN = 'shizhen'
DEFAULT_TAGS = ['时政', '新闻联播']
APP_CODE_GONGKAO = 'gongkao'


def build_hanyu_matcher(words: list[tuple[int, str]]) -> list[dict[str, Any]]:
    """
    构建汉语词汇匹配自动机

    :param words: 词汇 ID 与名称列表
    :return:
    """
    nodes: list[dict[str, Any]] = [{'next': {}, 'fail': 0, 'out': []}]
    for word_id, word in words:
        current_index = 0
        for char in word:
            next_nodes = nodes[current_index]['next']
            if char not in next_nodes:
                next_nodes[char] = len(nodes)
                nodes.append({'next': {}, 'fail': 0, 'out': []})
            current_index = next_nodes[char]
        nodes[current_index]['out'].append(word_id)

    queue: deque[int] = deque()
    for next_index in nodes[0]['next'].values():
        queue.append(next_index)

    while queue:
        current_index = queue.popleft()
        current_node = nodes[current_index]
        for char, next_index in current_node['next'].items():
            fail_index = current_node['fail']
            while fail_index and char not in nodes[fail_index]['next']:
                fail_index = nodes[fail_index]['fail']
            nodes[next_index]['fail'] = nodes[fail_index]['next'].get(char, 0)
            nodes[next_index]['out'].extend(nodes[nodes[next_index]['fail']]['out'])
            queue.append(next_index)

    return nodes


def match_hanyu_ids(text: str, matcher: list[dict[str, Any]]) -> set[int]:
    """
    匹配文本中的汉语词汇 ID

    :param text: 待扫描文本
    :param matcher: 汉语词汇匹配自动机
    :return:
    """
    matched_ids: set[int] = set()
    current_index = 0
    for char in text:
        while current_index and char not in matcher[current_index]['next']:
            current_index = matcher[current_index]['fail']
        current_index = matcher[current_index]['next'].get(char, 0)
        if matcher[current_index]['out']:
            matched_ids.update(matcher[current_index]['out'])
    return matched_ids


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
        'success': True,
        'fetched_count': 0,
        'created_count': 0,
        'updated_count': 0,
        'skipped_count': 0,
        'error_count': 0,
        'message': '',
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
                daily_date = datetime.strptime(add_time, '%Y-%m-%d').replace(tzinfo=timezone.tz_info).date()
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
                        app_code=APP_CODE_GONGKAO,  # 必填字段
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
                if existing.title != title:
                    update_obj.title = title
                    changed = True
                if existing.content_html != content_html:
                    update_obj.content_html = content_html
                    changed = True
                if existing.summary != summary:
                    update_obj.summary = summary
                    changed = True
                if existing.extra != extra:
                    update_obj.extra = extra
                    changed = True

                if changed:
                    await content_dao.update(db, existing.id, update_obj)
                    result['updated_count'] += 1
                else:
                    result['skipped_count'] += 1
            except Exception as exc:
                result['error_count'] += 1
                logger.error('Failed to process news record: %s', exc)
    return result


@celery_app.task(name='update_hanyu_frequency')
async def update_hanyu_frequency() -> dict[str, Any]:
    """更新汉语词汇使用频次"""
    result: dict[str, Any] = {
        'success': True,
        'total_count': 0,
        'updated_count': 0,
        'error_count': 0,
        'elapsed_seconds': 0,
        'message': '',
    }
    start_time = datetime.now()
    logger.info('开始统计汉语词汇使用频次（言语理解与表达题干与选项）...')

    try:
        async with async_db_session.begin() as db:
            idiom_sql = text("""
                SELECT id, name, frequency
                FROM gk_hanyu
                WHERE type = '成语'
                  AND NULLIF(BTRIM(name), '') IS NOT NULL
            """)
            idiom_rows = (await db.execute(idiom_sql)).mappings().all()
            result['total_count'] = len(idiom_rows)

            target_text_sql = text("""
                WITH target_questions AS (
                    SELECT q.id, q.stem, q.options
                    FROM study_question q
                    WHERE q.knowledge_point IS NOT NULL
                      AND q.knowledge_point::text LIKE '%言语理解与表达%'
                ),
                target_texts AS (
                    SELECT
                        tq.id AS question_id,
                        tq.stem AS content
                    FROM target_questions tq
                    WHERE NULLIF(BTRIM(tq.stem), '') IS NOT NULL

                    UNION ALL

                    SELECT
                        tq.id AS question_id,
                        option_item.item ->> 'content' AS content
                    FROM target_questions tq
                    CROSS JOIN LATERAL jsonb_array_elements(
                        COALESCE(tq.options, '[]'::jsonb)
                    ) AS option_item(item)
                    WHERE COALESCE(option_item.item ->> 'is_active', 'true') <> 'false'
                      AND NULLIF(BTRIM(option_item.item ->> 'content'), '') IS NOT NULL
                )
                SELECT question_id, content
                FROM target_texts
            """)
            text_rows = (await db.execute(target_text_sql)).mappings().all()
            target_text_count = len(text_rows)

            matcher = build_hanyu_matcher([(int(row['id']), str(row['name'])) for row in idiom_rows])
            frequency_map = {int(row['id']): 0 for row in idiom_rows}
            question_hanyu_ids: dict[int, set[int]] = {}
            for row in text_rows:
                content = strip_html_tags(str(row['content'] or ''))
                if not content:
                    continue
                question_id = int(row['question_id'])
                question_matches = question_hanyu_ids.setdefault(question_id, set())
                question_matches.update(match_hanyu_ids(content, matcher))

            for matched_ids in question_hanyu_ids.values():
                for word_id in matched_ids:
                    frequency_map[word_id] += 1

            update_params: list[dict[str, int]] = []
            for row in idiom_rows:
                word_id = int(row['id'])
                frequency = frequency_map[word_id]
                if int(row['frequency'] or 0) == frequency:
                    continue
                update_params.append({'id': word_id, 'frequency': frequency})

            if update_params:
                await db.execute(
                    text("""
                        UPDATE gk_hanyu
                        SET frequency = :frequency
                        WHERE id = :id
                    """),
                    update_params,
                )
            result['updated_count'] = len(update_params)

        elapsed = (datetime.now() - start_time).total_seconds()
        result['elapsed_seconds'] = round(elapsed, 2)
        result['message'] = (
            f'频次统计完成（言语理解与表达题干与选项）: 总计 {result["total_count"]} 个成语, '
            f'扫描 {len(question_hanyu_ids)} 道题 / {target_text_count} 段题干选项文本, '
            f'更新 {result["updated_count"]} 条记录, '
            f'耗时 {result["elapsed_seconds"]} 秒'
        )
        logger.info(result['message'])
        return result
    except Exception as exc:
        elapsed = (datetime.now() - start_time).total_seconds()
        result['success'] = False
        result['error_count'] = 1
        result['elapsed_seconds'] = round(elapsed, 2)
        result['message'] = f'频次统计失败: {exc}'
        logger.exception('汉语词汇频次统计失败')
        return result
