#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import asyncio
import re

from sqlalchemy import select

from backend.app.question_bank.model import QuestionBank
from backend.database.db import async_db_session

YEAR_RE = re.compile(r"(?<!\\d)(19\\d{2}|20\\d{2})(?!\\d)")


def _extract_year(text: str) -> int | None:
    """
    从文本中提取 4 位年份。

    :param text: 文本
    :return:
    """
    if not text:
        return None
    match = YEAR_RE.search(text)
    if not match:
        return None
    try:
        year = int(match.group(1))
    except Exception:
        return None
    if 1900 <= year <= 2100:
        return year
    return None


async def _run(*, dry_run: bool, limit: int, updated_by: int) -> None:
    """
    回填题库 year 字段。

    :param dry_run: 是否演练模式
    :param limit: 最大处理数量，0 表示不限制
    :param updated_by: updated_by 写入值
    :return:
    """
    scanned = 0
    updated = 0

    async with async_db_session() as db:
        stmt = (
            select(QuestionBank)
            .where(QuestionBank.bank_type == 2)
            .where(QuestionBank.year.is_(None))
            .order_by(QuestionBank.id.asc())
        )
        rows = (await db.execute(stmt)).scalars().all()

        for bank in rows:
            scanned += 1
            name = str(getattr(bank, "name", "") or "")
            code = str(getattr(bank, "code", "") or "")
            desc = str(getattr(bank, "desc", "") or "")

            year = _extract_year(name) or _extract_year(code) or _extract_year(desc)
            if year is None:
                continue

            bank.year = year
            bank.updated_by = updated_by
            updated += 1

            if limit > 0 and updated >= limit:
                break

        if dry_run:
            await db.rollback()
        else:
            await db.commit()

    print(f"[BANK_YEAR_BACKFILL] scanned={scanned} updated={updated} dry_run={'true' if dry_run else 'false'}")


def main() -> None:
    """回填题库 year 字段（从 name/code/desc 提取）。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="演练模式，不提交数据库")
    parser.add_argument("--limit", type=int, default=0, help="最多回填多少条（0=不限制）")
    parser.add_argument("--updated-by", type=int, default=1, help="updated_by 写入的用户 ID")
    args = parser.parse_args()

    asyncio.run(_run(dry_run=bool(args.dry_run), limit=max(0, int(args.limit)), updated_by=int(args.updated_by)))


if __name__ == "__main__":
    main()

