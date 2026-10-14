"""Backfill question-bank V2 knowledge mastery from historical graded attempts.

Run this only after the knowledge-mastery migration has been applied.  The
script is intentionally explicit and idempotent: attempt snapshots are unique
per attempt/system/point and delayed evidence is guarded by ``evidence_applied``.
"""

from __future__ import annotations

import argparse
import asyncio

from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING

from sqlalchemy import and_, delete, or_, select, update

from backend.app.question_bank_v2.model.mastery import (
    QbQuestionAttemptKnowledgePoint,
    QbUserKnowledgeMastery,
)
from backend.app.question_bank_v2.model.practice import (
    QbPracticeSessionItem,
    QbQuestionAttempt,
)
from backend.app.question_bank_v2.model.question import QbQuestion
from backend.app.question_bank_v2.service.knowledge_mastery_service import knowledge_mastery_service
from backend.database.db import async_db_session

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class BackfillBatch:
    attempts: list[QbQuestionAttempt]
    max_scores: list[Decimal]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='回填题库 V2 知识点掌握度投影')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='只统计，不写入数据库（默认）')
    mode.add_argument('--commit', action='store_true', help='提交回填结果')
    parser.add_argument('--rebuild', action='store_true', help='提交前清空指定范围投影并重放全部历史证据')
    parser.add_argument('--batch-size', type=int, default=500, help='每批处理数量，默认 500')
    parser.add_argument('--user-id', type=int, help='只回填指定用户')
    parser.add_argument('--limit', type=int, help='最多处理多少条作答事实')
    return parser.parse_args()


async def prepare_rebuild(db: AsyncSession, *, user_id: int | None) -> None:
    snapshot_filter = [QbQuestionAttemptKnowledgePoint.deleted == 0]
    mastery_filter = [QbUserKnowledgeMastery.deleted == 0]
    if user_id is not None:
        snapshot_filter.append(QbQuestionAttemptKnowledgePoint.user_id == user_id)
        mastery_filter.append(QbUserKnowledgeMastery.user_id == user_id)
    await db.execute(
        update(QbQuestionAttemptKnowledgePoint)
        .where(*snapshot_filter)
        .values(evidence_applied=False)
    )
    await db.execute(delete(QbUserKnowledgeMastery).where(*mastery_filter))
    await db.commit()


async def fetch_batch(
    db: AsyncSession,
    *,
    batch_size: int,
    user_id: int | None,
    last_time: datetime | None,
    last_id: int | None,
    remaining: int | None,
) -> BackfillBatch:
    stmt = (
        select(QbQuestionAttempt, QbPracticeSessionItem.max_score, QbQuestion.default_score)
        .join(QbQuestion, QbQuestion.id == QbQuestionAttempt.question_id)
        .outerjoin(QbPracticeSessionItem, QbPracticeSessionItem.id == QbQuestionAttempt.session_item_id)
        .where(
            QbQuestionAttempt.deleted == 0,
            QbQuestionAttempt.grading_status == 'graded',
            QbQuestion.deleted == 0,
        )
        .order_by(QbQuestionAttempt.submitted_time, QbQuestionAttempt.id)
        .limit(min(batch_size, remaining) if remaining is not None else batch_size)
    )
    if user_id is not None:
        stmt = stmt.where(QbQuestionAttempt.user_id == user_id)
    if last_time is not None and last_id is not None:
        stmt = stmt.where(
            or_(
                QbQuestionAttempt.submitted_time > last_time,
                and_(
                    QbQuestionAttempt.submitted_time == last_time,
                    QbQuestionAttempt.id > last_id,
                ),
            )
        )
    rows = (await db.execute(stmt)).all()
    return BackfillBatch(
        attempts=[row[0] for row in rows],
        max_scores=[Decimal(row[1] if row[1] is not None else row[2]) for row in rows],
    )


async def backfill(
    db: AsyncSession,
    *,
    dry_run: bool,
    batch_size: int,
    user_id: int | None,
    limit: int | None,
) -> int:
    processed = 0
    last_time: datetime | None = None
    last_id: int | None = None
    remaining = limit

    while remaining is None or remaining > 0:
        batch = await fetch_batch(
            db,
            batch_size=batch_size,
            user_id=user_id,
            last_time=last_time,
            last_id=last_id,
            remaining=remaining,
        )
        if not batch.attempts:
            break

        if not dry_run:
            for attempt, max_score in zip(batch.attempts, batch.max_scores, strict=True):
                session_item = SimpleNamespace(max_score=max_score)
                await knowledge_mastery_service.apply_attempt(
                    db,
                    attempt=attempt,
                    session_item=session_item,
                )
            await db.commit()

        processed += len(batch.attempts)
        if remaining is not None:
            remaining -= len(batch.attempts)
        last_attempt = batch.attempts[-1]
        last_time = last_attempt.submitted_time
        last_id = last_attempt.id
        print(f'processed={processed} dry_run={dry_run}')

    if dry_run:
        await db.rollback()
    return processed


async def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise SystemExit('--batch-size 必须大于 0')
    if args.limit is not None and args.limit <= 0:
        raise SystemExit('--limit 必须大于 0')
    if args.rebuild and not args.commit:
        raise SystemExit('--rebuild 必须与 --commit 一起使用')
    dry_run = not args.commit
    async with async_db_session() as db:
        if args.rebuild:
            await prepare_rebuild(db, user_id=args.user_id)
        processed = await backfill(
            db,
            dry_run=dry_run,
            batch_size=args.batch_size,
            user_id=args.user_id,
            limit=args.limit,
        )
    print(f'completed processed={processed} dry_run={dry_run}')
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
