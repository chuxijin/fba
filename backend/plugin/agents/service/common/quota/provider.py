#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.schema.engine import Decision
from backend.app.access.service.resource_access_service import resource_access_service
from backend.app.access.service.resource_profiles import (
    AGENT_ENGLISH_ESSAY_GRADE_PROFILE_CODE,
    AGENT_INTERVIEW_GRADE_PROFILE_CODE,
    AGENT_SHENLUN_GRADE_PROFILE_CODE,
    AGENT_XINGCE_GRADE_PROFILE_CODE,
)
from backend.common.exception import errors
from backend.plugin.agents.schema import AgentType

AGENT_RESOURCE_TYPE: dict[AgentType, str] = {
    AgentType.shenlun: 'agent_shenlun',
    AgentType.english_essay: 'agents.grading',
    AgentType.xingce: 'agents.grading',
    AgentType.interview: 'agents.grading',
}

AGENT_RESOURCE_IDS: dict[AgentType, int] = {
    AgentType.shenlun: 1,
    AgentType.english_essay: 2,
    AgentType.xingce: 3,
    AgentType.interview: 4,
}

AGENT_RESOURCE_PROFILE_CODES: dict[AgentType, str] = {
    AgentType.shenlun: AGENT_SHENLUN_GRADE_PROFILE_CODE,
    AgentType.english_essay: AGENT_ENGLISH_ESSAY_GRADE_PROFILE_CODE,
    AgentType.xingce: AGENT_XINGCE_GRADE_PROFILE_CODE,
    AgentType.interview: AGENT_INTERVIEW_GRADE_PROFILE_CODE,
}


class QuotaProvider:
    """Agent 权益适配层"""

    async def ensure_quota(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        agent_type: AgentType,
    ) -> Decision:
        """
        启动前权益校验，不扣减

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param agent_type: agent 类型
        :return:
        """
        return await resource_access_service.ensure(
            db,
            profile_code=self._resolve_profile_code(agent_type),
            user_id=user_id,
        )

    async def consume_quota(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        agent_type: AgentType,
    ) -> Decision:
        """
        任务成功完成后扣减权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param agent_type: agent 类型
        :return:
        """
        return await resource_access_service.consume(
            db,
            profile_code=self._resolve_profile_code(agent_type),
            user_id=user_id,
            raise_on_deny=False,
        )

    @staticmethod
    def _resolve_profile_code(agent_type: AgentType) -> str:
        """
        解析 agent 类型对应的档案编码

        :param agent_type: agent 类型
        :return:
        """
        profile_code = AGENT_RESOURCE_PROFILE_CODES.get(agent_type)
        if profile_code is None:
            raise errors.ServerError(msg=f'未配置 agent 类型对应的资源权益档案: {agent_type}')
        return profile_code


quota_provider: QuotaProvider = QuotaProvider()
