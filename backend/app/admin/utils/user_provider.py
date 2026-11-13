from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model import User
from backend.app.admin.service.user_service import user_service


async def get_current_user(db: AsyncSession, pk: int) -> User:
    """自定义调用方的兼容入口，用户可用性校验由 admin 服务统一实现。"""
    return await user_service.get_available(db=db, pk=pk)
