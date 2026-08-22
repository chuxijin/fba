from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.agent.model import AgentRun, AgentRunStep


class CRUDAgentRun(CRUDPlus[AgentRun]):
    """Agent 运行数据库操作类"""

    async def get_owned(self, db: AsyncSession, *, run_id: int, user_id: int) -> AgentRun | None:
        stmt = select(self.model).where(self.model.id == run_id, self.model.user_id == user_id)
        return (await db.execute(stmt)).scalars().first()

    async def get_by_idempotency(self, db: AsyncSession, *, key: str) -> AgentRun | None:
        stmt = select(self.model).where(self.model.idempotency_key == key)
        return (await db.execute(stmt)).scalars().first()

    async def list_recoverable(
        self,
        db: AsyncSession,
        *,
        agent_key: str,
        stale_before: datetime,
        limit: int = 100,
    ) -> list[AgentRun]:
        """获取启动时需要恢复的排队任务和陈旧运行任务。"""
        stmt = (
            select(self.model)
            .where(
                self.model.agent_key == agent_key,
                self.model.deleted == 0,
                or_(
                    self.model.status == 'queued',
                    and_(
                        self.model.status == 'running',
                        or_(
                            self.model.updated_time < stale_before,
                            and_(
                                self.model.updated_time.is_(None),
                                or_(self.model.started_time.is_(None), self.model.started_time < stale_before),
                            ),
                        ),
                    ),
                ),
            )
            .order_by(self.model.created_time.asc(), self.model.id.asc())
            .limit(max(1, min(limit, 500)))
        )
        return list((await db.execute(stmt)).scalars().all())

    async def claim_for_execution(
        self,
        db: AsyncSession,
        *,
        run_id: int,
        user_id: int,
        stale_before: datetime,
        started_time: datetime,
    ) -> bool:
        """原子认领排队或陈旧运行，避免多进程重复执行。"""
        stmt = (
            update(self.model)
            .where(
                self.model.id == run_id,
                self.model.user_id == user_id,
                self.model.deleted == 0,
                or_(
                    self.model.status == 'queued',
                    and_(
                        self.model.status == 'running',
                        or_(
                            self.model.updated_time < stale_before,
                            and_(
                                self.model.updated_time.is_(None),
                                or_(self.model.started_time.is_(None), self.model.started_time < stale_before),
                            ),
                        ),
                    ),
                ),
            )
            .values(
                status='running',
                stage='loading_context',
                progress=0.1,
                started_time=started_time,
                updated_time=started_time,
                finished_time=None,
                error_code=None,
                error_message=None,
            )
        )
        result = await db.execute(stmt)
        return result.rowcount == 1

    async def requeue_interrupted(self, db: AsyncSession, *, run_id: int, user_id: int) -> bool:
        """服务正常关闭时释放本进程已认领但未完成的运行。"""
        stmt = (
            update(self.model)
            .where(
                self.model.id == run_id,
                self.model.user_id == user_id,
                self.model.status == 'running',
                self.model.deleted == 0,
            )
            .values(
                status='queued',
                stage='recovery_pending',
                error_code='RunInterrupted',
                error_message='服务关闭导致 Agent 运行中断，已进入自动恢复队列。',
                finished_time=None,
                updated_time=func.now(),
            )
        )
        result = await db.execute(stmt)
        return result.rowcount == 1

    async def touch_running(self, db: AsyncSession, *, run_id: int, user_id: int) -> bool:
        """刷新已认领运行的心跳时间。"""
        stmt = (
            update(self.model)
            .where(
                self.model.id == run_id,
                self.model.user_id == user_id,
                self.model.status == 'running',
                self.model.deleted == 0,
            )
            .values(updated_time=func.now())
        )
        result = await db.execute(stmt)
        return result.rowcount == 1

    async def next_step_no(self, db: AsyncSession, *, run_id: int) -> int:
        """获取运行轨迹的下一个序号，支持断点恢复后继续追加审计。"""
        stmt = select(func.coalesce(func.max(AgentRunStep.step_no), 0) + 1).where(AgentRunStep.run_id == run_id)
        return int((await db.execute(stmt)).scalar_one())

    async def create_run(self, db: AsyncSession, *, data: dict[str, Any]) -> AgentRun:
        run = self.model(**data)
        try:
            async with db.begin_nested():
                db.add(run)
                await db.flush()
        except IntegrityError:
            existing = await self.get_by_idempotency(db, key=str(data['idempotency_key']))
            if existing is None:
                raise
            return existing
        else:
            return run

    async def add_step(self, db: AsyncSession, *, data: dict[str, Any]) -> AgentRunStep:
        step = AgentRunStep(**data)
        db.add(step)
        await db.flush()
        return step

    async def list_steps(self, db: AsyncSession, *, run_id: int) -> list[AgentRunStep]:
        stmt = select(AgentRunStep).where(AgentRunStep.run_id == run_id).order_by(AgentRunStep.step_no.asc())
        return list((await db.execute(stmt)).scalars().all())


agent_run_dao = CRUDAgentRun(AgentRun)
