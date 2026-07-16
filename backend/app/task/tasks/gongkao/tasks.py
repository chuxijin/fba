#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import re

from collections import deque
from datetime import date, datetime, time
from typing import Any

import akshare as ak

from sqlalchemy import text

from backend.app.content.crud.crud_content import content_dao
from backend.app.content.schema.content import CreateContentParam, UpdateContentParam
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)

SYSTEM_USER_ID = 1
CONTENT_TYPE_SHIZHEN = 'shizhen'
DEFAULT_TAGS = ['时政', '新闻联播']
APP_CODE_GONGKAO = 'gongkao'
CCTV_NEWS_URL = 'https://tv.cctv.com/lm/xwlb/'


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
    """构建时政内容 slug"""
    return f'shizhen-{daily_date.isoformat()}'


def build_news_html(news_items: list[dict[str, str]]) -> str:
    """将多条新闻组合为 HTML"""
    parts: list[str] = []
    for item in news_items:
        parts.append(f'<h3>{item["title"]}</h3>')
        for paragraph in item['content'].split('\n'):
            paragraph = paragraph.strip()
            if paragraph:
                parts.append(f'<p style="text-align: justify;">{paragraph}</p>')
    return '\n'.join(parts)


def build_news_summary(news_items: list[dict[str, str]]) -> str:
    """从新闻标题构建摘要"""
    summary = '；'.join(item['title'] for item in news_items)
    if len(summary) > 500:
        summary = f'{summary[:497].rstrip()}...'
    return summary


def strip_html_tags(content: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


@celery_app.task(name='gongkao:sync_daily_news_to_shizhen', bind=True)
async def sync_daily_news_to_shizhen(self) -> dict[str, Any]:
    """同步每日新闻联播文字稿到时政内容"""
    today = timezone.now().date()
    date_str = today.strftime('%Y%m%d')

    result: dict[str, Any] = {
        'success': True,
        'date': date_str,
        'news_count': 0,
        'action': '',
        'message': '',
    }

    try:
        df = await asyncio.to_thread(ak.news_cctv, date=date_str)
    except Exception as exc:
        raise RuntimeError(f'AKShare 获取新闻联播失败: {exc}') from exc

    if df is None or df.empty:
        result['message'] = f'{date_str} 暂无新闻联播数据'
        return result

    news_items = [
        {'title': str(row['title']), 'content': str(row['content'])}
        for _, row in df.iterrows()
    ]
    result['news_count'] = len(news_items)

    slug = build_content_slug(today)
    title = f'新闻联播 {today.isoformat()}'
    content_html = build_news_html(news_items)
    summary = build_news_summary(news_items)
    publish_time = datetime.combine(today, time.min)
    extra: dict[str, Any] = {
        'content_type': CONTENT_TYPE_SHIZHEN,
        'daily_date': today.isoformat(),
        'origin_url': CCTV_NEWS_URL,
    }

    async with async_db_session.begin() as db:
        existing = await content_dao.get_by_slug(db, slug)

        if not existing:
            create_obj = CreateContentParam(
                app_code=APP_CODE_GONGKAO,
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
            await content_dao.create_model(db, create_obj, created_by=SYSTEM_USER_ID)
            result['action'] = 'created'
        else:
            update_obj = UpdateContentParam()
            changed = False
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
                await content_dao.update_model(db, existing.id, update_obj)
                result['action'] = 'updated'
            else:
                result['action'] = 'skipped'

    result['message'] = f'{date_str} 新闻联播 {len(news_items)} 条, {result["action"]}'
    return result


@celery_app.task(name='gongkao:update_hanyu_frequency')
async def update_hanyu_frequency() -> dict[str, Any]:
    """更新汉语词汇相关题目 ID 列表"""
    result: dict[str, Any] = {
        'success': True,
        'total_count': 0,
        'updated_count': 0,
        'error_count': 0,
        'elapsed_seconds': 0,
        'message': '',
    }
    start_time = datetime.now()
    logger.info('开始统计汉语词汇相关题目（逻辑填空题干与选项）...')

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
                      AND q.knowledge_point::text LIKE '%逻辑填空%'
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
            frequency_map: dict[int, set[int]] = {int(row['id']): set() for row in idiom_rows}
            question_hanyu_ids: dict[int, set[int]] = {}
            for row in text_rows:
                content = strip_html_tags(str(row['content'] or ''))
                if not content:
                    continue
                question_id = int(row['question_id'])
                question_matches = question_hanyu_ids.setdefault(question_id, set())
                question_matches.update(match_hanyu_ids(content, matcher))

            for question_id, matched_ids in question_hanyu_ids.items():
                for word_id in matched_ids:
                    frequency_map[word_id].add(question_id)

            update_params: list[dict[str, Any]] = []
            for row in idiom_rows:
                word_id = int(row['id'])
                question_ids = sorted(frequency_map[word_id])
                old_freq = row['frequency']
                old_count = len(old_freq) if isinstance(old_freq, list) else (old_freq or 0)
                if old_count == len(question_ids):
                    continue
                update_params.append({
                    'id': word_id,
                    'frequency': question_ids if question_ids else None,
                })

            if update_params:
                import json
                for param in update_params:
                    await db.execute(
                        text("UPDATE gk_hanyu SET frequency = CAST(:freq AS jsonb) WHERE id = :hid"),
                        {'freq': json.dumps(param['frequency']), 'hid': param['id']},
                    )
            result['updated_count'] = len(update_params)

        elapsed = (datetime.now() - start_time).total_seconds()
        result['elapsed_seconds'] = round(elapsed, 2)
        result['message'] = (
            f'频次统计完成（逻辑填空题干与选项）: 总计 {result["total_count"]} 个成语, '
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
