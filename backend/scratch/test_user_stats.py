import asyncio
from datetime import timedelta
from sqlalchemy import select, func
from backend.database.db import async_db_session
from backend.app.admin.model.user import User
from backend.utils.timezone import timezone

async def test():
    async with async_db_session() as db:
        # 1. 统计总用户数
        stmt_total = select(func.count(User.id))
        total_users = (await db.execute(stmt_total)).scalar_one()
        print(f"Total Users: {total_users}")

        # 2. 今日新增
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        stmt_today = select(func.count(User.id)).where(User.join_time >= today_start)
        today_new_users = (await db.execute(stmt_today)).scalar_one()
        print(f"Today New Users: {today_new_users}")

        # 3. 统计近 30 天趋势数据
        thirty_days_ago = today_start - timedelta(days=30)
        stmt_records = select(User.join_time).where(User.join_time >= thirty_days_ago)
        records = (await db.execute(stmt_records)).scalars().all()
        print(f"Records Count: {len(records)}")


if __name__ == '__main__':
    asyncio.run(test())
