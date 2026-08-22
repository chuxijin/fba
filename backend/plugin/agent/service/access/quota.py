from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.schema.engine import Decision
from backend.app.access.service.resource_access_service import resource_access_service
from backend.app.access.service.resource_profiles import (
    AGENT_SHENLUN_COACH_PROFILE_CODE,
    AGENT_SHENLUN_GRADE_PROFILE_CODE,
)


class AgentQuotaService:
    """新 Agent 平台额度适配服务"""

    @staticmethod
    async def ensure_shenlun_grading(*, db: AsyncSession, user_id: int) -> Decision:
        """预检申论批改额度，不产生扣减。"""
        return await resource_access_service.ensure(
            db,
            profile_code=AGENT_SHENLUN_GRADE_PROFILE_CODE,
            user_id=user_id,
        )

    @staticmethod
    async def consume_shenlun_grading(
        *,
        db: AsyncSession,
        user_id: int,
        run_id: int,
    ) -> Decision:
        """在运行被认领后幂等消耗一次申论批改额度。"""
        return await resource_access_service.consume(
            db,
            profile_code=AGENT_SHENLUN_GRADE_PROFILE_CODE,
            user_id=user_id,
            source_ref=AgentQuotaService.source_ref(run_id),
        )

    @staticmethod
    async def refund_shenlun_grading(
        *,
        db: AsyncSession,
        user_id: int,
        run_id: int,
        decision: Decision,
    ) -> None:
        """最终失败时按原扣减账本精确退款。"""
        await resource_access_service.refund(
            db,
            profile_code=AGENT_SHENLUN_GRADE_PROFILE_CODE,
            user_id=user_id,
            decision=decision,
            source_ref=f'{AgentQuotaService.source_ref(run_id)}:refund',
        )

    @staticmethod
    def source_ref(run_id: int) -> str:
        return f'shenlun_grading_run:{run_id}'

    @staticmethod
    async def consume_shenlun_coach(*, db: AsyncSession, user_id: int, request_ref: str) -> Decision:
        """幂等消耗一次申论教练对话额度。"""
        return await resource_access_service.consume(
            db,
            profile_code=AGENT_SHENLUN_COACH_PROFILE_CODE,
            user_id=user_id,
            source_ref=request_ref,
        )

    @staticmethod
    async def refund_shenlun_coach(
        *,
        db: AsyncSession,
        user_id: int,
        request_ref: str,
        decision: Decision,
    ) -> None:
        """教练响应生成失败时精确退款。"""
        await resource_access_service.refund(
            db,
            profile_code=AGENT_SHENLUN_COACH_PROFILE_CODE,
            user_id=user_id,
            decision=decision,
            source_ref=f'{request_ref}:refund',
        )

    @staticmethod
    def get_state(config_snapshot: dict[str, Any] | None) -> dict[str, Any]:
        state = (config_snapshot or {}).get('quota')
        return dict(state) if isinstance(state, dict) else {}

    @staticmethod
    def set_state(config_snapshot: dict[str, Any] | None, state: dict[str, Any]) -> dict[str, Any]:
        config = dict(config_snapshot or {})
        config['quota'] = state
        return config

    @staticmethod
    def acquired_state(*, run_id: int, decision: Decision) -> dict[str, Any]:
        return {
            'profile_code': AGENT_SHENLUN_GRADE_PROFILE_CODE,
            'source_ref': AgentQuotaService.source_ref(run_id),
            'status': 'acquired',
            'decision': decision.model_dump(mode='json'),
        }

    @staticmethod
    def restore_decision(state: dict[str, Any]) -> Decision | None:
        payload = state.get('decision')
        if not isinstance(payload, dict):
            return None
        return Decision.model_validate(payload)


agent_quota_service = AgentQuotaService()
