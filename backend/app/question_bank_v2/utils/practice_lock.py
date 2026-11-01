"""练习写入统一先锁用户，避免跨会话首次建统计/掌握度行的唯一键竞争。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model.user import User


async def lock_practice_user(db: AsyncSession, user_id: int) -> None:
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())
