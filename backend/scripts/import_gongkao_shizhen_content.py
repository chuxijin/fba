#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.gongkao.crud.crud_content import content_dao  # noqa: E402
from backend.app.gongkao.schema.content import CreateContentParam, UpdateContentParam  # noqa: E402
from backend.app.task.tasks.gongkao.tasks import (  # noqa: E402
    DEFAULT_TAGS,
    NEWS_API_TIMEOUT,
    NEWS_API_URL,
    SYSTEM_USER_ID,
    build_content_slug,
    build_extra,
    build_summary,
    normalize_news_html,
)
from backend.database.db import async_db_session  # noqa: E402


@dataclass
class ImportStats:
    """Import stats."""

    fetched_pages: int = 0
    fetched_records: int = 0
    matched_records: int = 0
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    error_count: int = 0


async def fetch_news_page(client: httpx.AsyncClient, page_num: int, page_size: int) -> list[dict[str, Any]]:
    """
    Fetch one remote page.

    :param client: http client
    :param page_num: page number
    :param page_size: page size
    :return:
    """
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
    payload = response.json()
    if payload.get('code') != 0:
        raise RuntimeError(f"saduck api error: {payload.get('message', 'unknown error')}")

    result = payload.get('result') or {}
    records = result.get('records') or []
    if not isinstance(records, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in records:
        if isinstance(item, dict):
            normalized.append(item)
    return normalized


def parse_daily_date(record: dict[str, Any]) -> date | None:
    """
    Parse record daily date.

    :param record: remote record
    :return:
    """
    add_time = str(record.get('addTime') or '').strip()
    if not add_time:
        return None

    try:
        return datetime.strptime(add_time, '%Y-%m-%d').date()
    except ValueError:
        return None


async def collect_records_since(
    start_date: date,
    end_date: date | None,
    page_size: int,
    max_pages: int,
) -> tuple[list[dict[str, Any]], ImportStats]:
    """
    Collect records in date range.

    :param start_date: inclusive start date
    :param end_date: inclusive end date
    :param page_size: page size
    :param max_pages: max pages
    :return:
    """
    stats = ImportStats()
    matched_records: list[dict[str, Any]] = []
    timeout = httpx.Timeout(timeout=float(NEWS_API_TIMEOUT))

    async with httpx.AsyncClient(timeout=timeout) as client:
        for page_num in range(1, max_pages + 1):
            records = await fetch_news_page(client, page_num=page_num, page_size=page_size)
            stats.fetched_pages += 1
            stats.fetched_records += len(records)
            if not records:
                break

            page_has_match = False
            parsed_dates: list[date] = []
            for record in records:
                daily_date = parse_daily_date(record)
                if daily_date is None:
                    continue
                parsed_dates.append(daily_date)
                if daily_date < start_date:
                    continue
                if end_date is not None and daily_date > end_date:
                    continue
                matched_records.append(record)
                page_has_match = True

            if not page_has_match:
                if not parsed_dates:
                    break
                oldest_date = min(parsed_dates)
                if oldest_date < start_date:
                    break

    deduped: dict[str, dict[str, Any]] = {}
    for record in matched_records:
        daily_date = parse_daily_date(record)
        if daily_date is None:
            continue

        slug = build_content_slug(daily_date)
        current = deduped.get(slug)
        if current is None:
            deduped[slug] = record
            continue

        current_id = int(current.get('id') or 0)
        record_id = int(record.get('id') or 0)
        if record_id < current_id:
            deduped[slug] = record

    ordered_records = sorted(
        deduped.values(),
        key=lambda item: (
            int(item.get('id') or 0),
            str(item.get('addTime') or ''),
        ),
    )
    stats.matched_records = len(ordered_records)
    return ordered_records, stats


async def upsert_record(record: dict[str, Any]) -> str:
    """
    Upsert one record into gk_content.

    :param record: remote record
    :return:
    """
    daily_date = parse_daily_date(record)
    if daily_date is None:
        raise ValueError('invalid addTime')

    slug = build_content_slug(daily_date)
    title = str(record.get('title') or f'news {daily_date.isoformat()}').strip()
    content_html = normalize_news_html(str(record.get('intro') or ''))
    summary = build_summary(content_html)
    publish_time = datetime.combine(daily_date, time.min)
    extra = build_extra(record, daily_date)

    async with async_db_session.begin() as db:
        existing = await content_dao.get_by_slug(db, slug)
        if existing is None:
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
            return 'created'

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
            return 'skipped'

        await content_dao.update(db, existing.id, update_obj, updated_by=SYSTEM_USER_ID)
        return 'updated'


def build_args() -> argparse.Namespace:
    """Build cli args."""
    parser = argparse.ArgumentParser(description='Import gongkao shizhen content from saduck')
    parser.add_argument('--start-date', default='2026-01-01', help='inclusive start date, format: YYYY-MM-DD')
    parser.add_argument('--end-date', default=None, help='inclusive end date, format: YYYY-MM-DD')
    parser.add_argument('--page-size', type=int, default=20, help='remote page size')
    parser.add_argument('--max-pages', type=int, default=200, help='max remote pages to scan')
    parser.add_argument('--dry-run', action='store_true', help='only show matched records, do not write db')
    return parser.parse_args()


async def main() -> int:
    """Run import."""
    args = build_args()
    try:
        start_date = date.fromisoformat(args.start_date)
    except ValueError:
        print(f'[ERROR] invalid start date: {args.start_date}')
        return 1

    end_date: date | None = None
    if args.end_date:
        try:
            end_date = date.fromisoformat(args.end_date)
        except ValueError:
            print(f'[ERROR] invalid end date: {args.end_date}')
            return 1
        if end_date < start_date:
            print(f'[ERROR] end date {args.end_date} is earlier than start date {args.start_date}')
            return 1

    records, stats = await collect_records_since(
        start_date=start_date,
        end_date=end_date,
        page_size=max(1, int(args.page_size)),
        max_pages=max(1, int(args.max_pages)),
    )
    print(
        f'[FETCH] pages={stats.fetched_pages} total_records={stats.fetched_records} '
        f'matched={stats.matched_records} start_date={start_date.isoformat()} '
        f'end_date={(end_date.isoformat() if end_date else "none")}'
    )

    if not records:
        print('[DONE] no matched records')
        return 0

    print('[ORDER] import order by remote id asc:')
    for record in records:
        print(
            f"  - remote_id={int(record.get('id') or 0)} "
            f"date={record.get('addTime')} title={str(record.get('title') or '').strip()}"
        )

    if args.dry_run:
        print('[DRY_RUN] skip database write')
        return 0

    for record in records:
        remote_id = int(record.get('id') or 0)
        daily_date = str(record.get('addTime') or '').strip()
        title = str(record.get('title') or '').strip()
        try:
            action = await upsert_record(record)
            if action == 'created':
                stats.created_count += 1
            elif action == 'updated':
                stats.updated_count += 1
            else:
                stats.skipped_count += 1
            print(f'[WRITE] remote_id={remote_id} date={daily_date} action={action} title={title}')
        except Exception as exc:
            stats.error_count += 1
            print(f'[ERROR] remote_id={remote_id} date={daily_date} title={title} error={exc!s}')

    print(
        f'[DONE] created={stats.created_count} updated={stats.updated_count} '
        f'skipped={stats.skipped_count} errors={stats.error_count}'
    )
    return 0 if stats.error_count == 0 else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
