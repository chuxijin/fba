#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性迁移：把机器人（bot 角色）的 v1 刷题快照折算写入 qbank_v2_user_practice_statistics。

用法：
    cd backend
    ..\\.venv\\Scripts\\python.exe scripts/migrate_bot_stats_v2.py

幂等：已存在 v2 投影的机器人会被跳过（不覆盖真实作答积累）。
"""

import asyncio
import sys

from pathlib import Path

from sqlalchemy import select

from backend.app.admin.model.m2m import user_role
from backend.app.admin.model.role import Role
from backend.app.question_bank.model import UserPracticeStats
from backend.app.question_bank_v2.model.statistics import QbUserPracticeStatistics
from backend.database.db import async_db_session
from backend.utils.timezone import timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BOT_ROLE_NAME = 'bot'


async def main() -> None:
    async with async_db_session() as db:
        role_id = await db.scalar(select(Role.id).where(Role.name == BOT_ROLE_NAME))
        if not role_id:
            print(f'未找到角色 "{BOT_ROLE_NAME}"，无事可做')
            return

        bot_ids = (await db.execute(select(user_role.c.user_id).where(user_role.c.role_id == role_id))).scalars().all()
        if not bot_ids:
            print('没有机器人用户，无事可做')
            return

        v1_rows = (
            (await db.execute(select(UserPracticeStats).where(UserPracticeStats.user_id.in_(bot_ids)))).scalars().all()
        )
        created = skipped = 0
        for row in v1_rows:
            exists = await db.scalar(
                select(QbUserPracticeStatistics.id).where(
                    QbUserPracticeStatistics.user_id == row.user_id,
                    QbUserPracticeStatistics.deleted == 0,
                )
            )
            if exists:
                skipped += 1
                continue
            db.add(
                QbUserPracticeStatistics(
                    user_id=row.user_id,
                    attempt_count=row.total_count,
                    graded_count=row.total_count,  # v1 快照口径即已判题数
                    correct_count=row.correct_count,
                    total_duration_ms=(row.total_duration or 0) * 1000,
                    practice_days=row.practice_days,
                    last_practice_date=row.last_practice_date,
                    streak_days=row.streak_days,
                    calculated_time=timezone.now(),
                )
            )
            created += 1

        await db.commit()
        print(f'迁移完成：新建 {created} 条，跳过（已存在）{skipped} 条，v1 快照缺失 {len(bot_ids) - len(v1_rows)} 条')


if __name__ == '__main__':
    asyncio.run(main())
