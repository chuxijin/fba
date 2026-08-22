from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import case, or_, select, update
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.agent.model import AgentCalibrationAnchor, AgentCalibrationPolicy

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CRUDAgentCalibrationAnchor(CRUDPlus[AgentCalibrationAnchor]):
    """Agent 校准锚点数据库操作类"""

    async def upsert(self, db: AsyncSession, *, data: dict[str, Any]) -> AgentCalibrationAnchor:
        stmt = select(self.model).where(
            self.model.agent_key == data['agent_key'],
            self.model.session_id == data['session_id'],
            self.model.deleted == 0,
        )
        anchor = (await db.execute(stmt)).scalars().first()
        if anchor is None:
            anchor = self.model(**data)
            db.add(anchor)
        else:
            for key, value in data.items():
                setattr(anchor, key, value)
        await db.flush()
        return anchor

    async def list_ready(self, db: AsyncSession, *, agent_key: str) -> list[AgentCalibrationAnchor]:
        stmt = (
            select(self.model)
            .where(
                self.model.agent_key == agent_key,
                self.model.status == 'ready',
                self.model.deleted == 0,
            )
            .order_by(self.model.created_time, self.model.id)
        )
        return list((await db.execute(stmt)).scalars().all())


class CRUDAgentCalibrationPolicy(CRUDPlus[AgentCalibrationPolicy]):
    """Agent 校准策略数据库操作类"""

    async def get_by_source(
        self,
        db: AsyncSession,
        *,
        agent_key: str,
        source_hash: str,
    ) -> AgentCalibrationPolicy | None:
        stmt = select(self.model).where(
            self.model.agent_key == agent_key,
            self.model.source_hash == source_hash,
            self.model.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def activate(
        self,
        db: AsyncSession,
        *,
        data: dict[str, Any],
    ) -> AgentCalibrationPolicy:
        active_key = f'{data["scope_type"]}:{data["scope_key"]}'
        await db.execute(
            update(self.model)
            .where(
                self.model.agent_key == data['agent_key'],
                self.model.active_key == active_key,
                self.model.deleted == 0,
            )
            .values(status='retired', active_key=None)
        )
        stmt = select(self.model).where(
            self.model.agent_key == data['agent_key'],
            self.model.source_hash == data['source_hash'],
            self.model.deleted == 0,
        )
        policy = (await db.execute(stmt)).scalars().first()
        if policy is None:
            policy = self.model(**data, status='active', active_key=active_key)
            db.add(policy)
        else:
            for key, value in data.items():
                setattr(policy, key, value)
            policy.status = 'active'
            policy.active_key = active_key
        await db.flush()
        return policy

    async def retire_scope(
        self,
        db: AsyncSession,
        *,
        agent_key: str,
        scope_type: str,
        scope_key: str,
    ) -> None:
        active_key = f'{scope_type}:{scope_key}'
        await db.execute(
            update(self.model)
            .where(
                self.model.agent_key == agent_key,
                self.model.active_key == active_key,
                self.model.deleted == 0,
            )
            .values(status='retired', active_key=None)
        )

    async def get_active(
        self,
        db: AsyncSession,
        *,
        agent_key: str,
        bank_revision_id: int | None,
        question_type: str,
    ) -> AgentCalibrationPolicy | None:
        scope_pairs = [('question_type', question_type), ('global', 'global')]
        if bank_revision_id is not None:
            scope_pairs.insert(0, ('bank_revision', str(bank_revision_id)))
        clauses = [
            (self.model.scope_type == scope_type) & (self.model.scope_key == scope_key)
            for scope_type, scope_key in scope_pairs
        ]
        priority = case(
            *[
                (
                    (self.model.scope_type == scope_type) & (self.model.scope_key == scope_key),
                    index,
                )
                for index, (scope_type, scope_key) in enumerate(scope_pairs)
            ],
            else_=len(scope_pairs),
        )
        stmt = (
            select(self.model)
            .where(
                self.model.agent_key == agent_key,
                self.model.status == 'active',
                self.model.deleted == 0,
                or_(*clauses),
            )
            .order_by(priority, self.model.id.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalars().first()


agent_calibration_anchor_dao = CRUDAgentCalibrationAnchor(AgentCalibrationAnchor)
agent_calibration_policy_dao = CRUDAgentCalibrationPolicy(AgentCalibrationPolicy)
