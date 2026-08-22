from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.agent.model import (
    ShenlunCoachMemory,
    ShenlunCoachMessage,
    ShenlunCoachSession,
    ShenlunTrainingPlan,
    ShenlunTrainingPlanItem,
)


class CRUDShenlunCoachSession(CRUDPlus[ShenlunCoachSession]):
    async def get_owned(self, db: AsyncSession, *, session_id: int, user_id: int) -> ShenlunCoachSession | None:
        stmt = select(self.model).where(
            self.model.id == session_id,
            self.model.user_id == user_id,
            self.model.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_owned_for_update(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        user_id: int,
    ) -> ShenlunCoachSession | None:
        stmt = (
            select(self.model)
            .where(
                self.model.id == session_id,
                self.model.user_id == user_id,
                self.model.deleted == 0,
            )
            .with_for_update()
        )
        return (await db.execute(stmt)).scalars().first()

    async def create_session(self, db: AsyncSession, *, data: dict[str, Any]) -> ShenlunCoachSession:
        session = self.model(**data)
        db.add(session)
        await db.flush()
        return session

    async def list_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ShenlunCoachSession]:
        stmt = select(self.model).where(self.model.user_id == user_id, self.model.deleted == 0)
        if status:
            stmt = stmt.where(self.model.status == status)
        stmt = stmt.order_by(self.model.updated_time.desc(), self.model.id.desc()).limit(max(1, min(limit, 100)))
        return list((await db.execute(stmt)).scalars().all())


class CRUDShenlunCoachMessage(CRUDPlus[ShenlunCoachMessage]):
    async def create_message(self, db: AsyncSession, *, data: dict[str, Any]) -> ShenlunCoachMessage:
        message = self.model(**data)
        db.add(message)
        await db.flush()
        return message

    async def list_recent(self, db: AsyncSession, *, session_id: int, limit: int = 20) -> list[ShenlunCoachMessage]:
        recent = (
            select(self.model)
            .where(self.model.session_id == session_id, self.model.deleted == 0)
            .order_by(self.model.created_time.desc(), self.model.id.desc())
            .limit(max(1, min(limit, 100)))
        )
        rows = list((await db.execute(recent)).scalars().all())
        rows.reverse()
        return rows


class CRUDShenlunCoachMemory(CRUDPlus[ShenlunCoachMemory]):
    async def list_user(self, db: AsyncSession, *, user_id: int, limit: int = 50) -> list[ShenlunCoachMemory]:
        stmt = (
            select(self.model)
            .where(self.model.user_id == user_id, self.model.deleted == 0)
            .order_by(self.model.confidence.desc(), self.model.updated_time.desc())
            .limit(max(1, min(limit, 200)))
        )
        return list((await db.execute(stmt)).scalars().all())

    async def upsert(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        memory_key: str,
        data: dict[str, Any],
    ) -> ShenlunCoachMemory:
        stmt = select(self.model).where(
            self.model.user_id == user_id,
            self.model.memory_key == memory_key,
            self.model.deleted == 0,
        )
        memory = (await db.execute(stmt)).scalars().first()
        if memory is None:
            memory = self.model(user_id=user_id, memory_key=memory_key, **data)
            db.add(memory)
        else:
            for key, value in data.items():
                setattr(memory, key, value)
        await db.flush()
        return memory


class CRUDShenlunTrainingPlan(CRUDPlus[ShenlunTrainingPlan]):
    async def create_plan(self, db: AsyncSession, *, data: dict[str, Any]) -> ShenlunTrainingPlan:
        plan = self.model(**data)
        db.add(plan)
        await db.flush()
        return plan

    async def get_owned(self, db: AsyncSession, *, plan_id: int, user_id: int) -> ShenlunTrainingPlan | None:
        stmt = select(self.model).where(
            self.model.id == plan_id,
            self.model.user_id == user_id,
            self.model.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def list_user(self, db: AsyncSession, *, user_id: int, limit: int = 20) -> list[ShenlunTrainingPlan]:
        stmt = (
            select(self.model)
            .where(self.model.user_id == user_id, self.model.deleted == 0)
            .order_by(self.model.created_time.desc(), self.model.id.desc())
            .limit(max(1, min(limit, 100)))
        )
        return list((await db.execute(stmt)).scalars().all())


class CRUDShenlunTrainingPlanItem(CRUDPlus[ShenlunTrainingPlanItem]):
    async def batch_create(self, db: AsyncSession, *, rows: list[dict[str, Any]]) -> list[ShenlunTrainingPlanItem]:
        items = [self.model(**row) for row in rows]
        db.add_all(items)
        await db.flush()
        return items

    async def list_plan(self, db: AsyncSession, *, plan_id: int) -> list[ShenlunTrainingPlanItem]:
        stmt = (
            select(self.model)
            .where(self.model.plan_id == plan_id, self.model.deleted == 0)
            .order_by(self.model.due_date.asc(), self.model.id.asc())
        )
        return list((await db.execute(stmt)).scalars().all())

    async def get_owned(self, db: AsyncSession, *, item_id: int, user_id: int) -> ShenlunTrainingPlanItem | None:
        stmt = select(self.model).where(
            self.model.id == item_id,
            self.model.user_id == user_id,
            self.model.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def complete(
        self,
        db: AsyncSession,
        *,
        item: ShenlunTrainingPlanItem,
        completed_time: datetime,
    ) -> None:
        item.status = 'completed'
        item.completed_time = completed_time
        await db.flush()


shenlun_coach_session_dao = CRUDShenlunCoachSession(ShenlunCoachSession)
shenlun_coach_message_dao = CRUDShenlunCoachMessage(ShenlunCoachMessage)
shenlun_coach_memory_dao = CRUDShenlunCoachMemory(ShenlunCoachMemory)
shenlun_training_plan_dao = CRUDShenlunTrainingPlan(ShenlunTrainingPlan)
shenlun_training_plan_item_dao = CRUDShenlunTrainingPlanItem(ShenlunTrainingPlanItem)
