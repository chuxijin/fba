from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.agent.model import AgentRubric


class CRUDAgentRubric(CRUDPlus[AgentRubric]):
    """Agent 评分基准缓存数据库操作类"""

    async def get_ready(
        self,
        db: AsyncSession,
        *,
        agent_key: str,
        question_id: int,
        reference_set_hash: str,
        source_hash: str,
        rubric_version: str,
    ) -> AgentRubric | None:
        stmt = select(self.model).where(
            self.model.agent_key == agent_key,
            self.model.question_id == question_id,
            self.model.reference_set_hash == reference_set_hash,
            self.model.source_hash == source_hash,
            self.model.rubric_version == rubric_version,
            self.model.status == 'ready',
        )
        return (await db.execute(stmt)).scalars().first()

    async def create_cache(self, db: AsyncSession, *, data: dict[str, Any]) -> AgentRubric:
        rubric = self.model(**data)
        try:
            async with db.begin_nested():
                db.add(rubric)
                await db.flush()
        except IntegrityError:
            cached = await self.get_ready(
                db,
                agent_key=str(data['agent_key']),
                question_id=int(data['question_id']),
                reference_set_hash=str(data['reference_set_hash']),
                source_hash=str(data['source_hash']),
                rubric_version=str(data['rubric_version']),
            )
            if cached is None:
                raise
            return cached
        else:
            return rubric

    async def list_latest_ready(
        self,
        db: AsyncSession,
        *,
        agent_key: str,
        question_ids: list[int],
    ) -> list[AgentRubric]:
        if not question_ids:
            return []
        latest = (
            select(self.model.question_id, func.max(self.model.id).label('rubric_id'))
            .where(
                self.model.agent_key == agent_key,
                self.model.question_id.in_(set(question_ids)),
                self.model.status == 'ready',
                self.model.deleted == 0,
            )
            .group_by(self.model.question_id)
            .subquery()
        )
        stmt = select(self.model).join(latest, latest.c.rubric_id == self.model.id).order_by(self.model.question_id)
        return list((await db.execute(stmt)).scalars().all())


agent_rubric_dao = CRUDAgentRubric(AgentRubric)
