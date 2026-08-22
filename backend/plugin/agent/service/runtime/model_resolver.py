from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.plugin.ai.model.model import AIModel
from backend.plugin.ai.model.provider import AIProvider

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def resolve_agent_model(*, db: AsyncSession, model_name: str | None = None) -> tuple[AIModel, AIProvider]:
    """Resolve an enabled model/provider pair shared by all Agent workflows."""
    name = model_name or 'gpt-5.4'
    stmt = (
        select(AIModel, AIProvider)
        .join(AIProvider, AIProvider.id == AIModel.provider_id)
        .where(
            AIModel.model_id == name,
            AIModel.status == 1,
            AIProvider.status == 1,
        )
        .order_by(AIModel.id.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise ValueError(f'未找到可用的 AI 模型：{name}')
    return row[0], row[1]
