from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.agent.model import AgentGradingFeedback, AgentRubric


class CRUDAgentGradingFeedback(CRUDPlus[AgentGradingFeedback]):
    """申论批改人工纠正数据库操作类"""

    async def upsert(self, db: AsyncSession, *, data: dict[str, Any]) -> AgentGradingFeedback:
        stmt = select(self.model).where(
            self.model.run_id == data['run_id'],
            self.model.point_key == data['point_key'],
            self.model.scope == data['scope'],
        )
        feedback = (await db.execute(stmt)).scalars().first()
        if feedback is None:
            feedback = self.model(**data)
            db.add(feedback)
        else:
            for key, value in data.items():
                setattr(feedback, key, value)
        await db.flush()
        return feedback

    async def list_question_feedback(self, db: AsyncSession, *, question_id: int) -> list[AgentGradingFeedback]:
        stmt = (
            select(self.model)
            .where(self.model.question_id == question_id, self.model.scope == 'question')
            .order_by(self.model.updated_time.desc(), self.model.id.desc())
            .limit(50)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def invalidate_question_rubrics(db: AsyncSession, *, question_id: int) -> None:
        await db.execute(
            update(AgentRubric)
            .where(AgentRubric.question_id == question_id, AgentRubric.status == 'ready')
            .values(status='stale')
        )


agent_grading_feedback_dao = CRUDAgentGradingFeedback(AgentGradingFeedback)
