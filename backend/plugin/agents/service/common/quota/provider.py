#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import ReasonCode, ResourceType
from backend.app.access.engine.decide import access_decision_engine
from backend.app.access.schema.engine import AccessContext, Decision
from backend.common.exception import errors
from backend.plugin.agents.schema import AgentType

AGENT_RESOURCE_TYPE: dict[AgentType, str] = {
    AgentType.shenlun: ResourceType.AGENT_SHENLUN,
}

AGENT_RESOURCE_IDS: dict[AgentType, int] = {
    AgentType.shenlun: 1,
    AgentType.english_essay: 2,
    AgentType.xingce: 3,
    AgentType.interview: 4,
}


class QuotaProvider:
    """Agent 权益封装"""

    async def ensure_quota(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        agent_type: AgentType,
    ) -> Decision:
        """
        启动前权益校验, 不扣减; 失败抛 ForbiddenError

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param agent_type: agent 类型
        :return:
        """
        ctx = AccessContext(
            user_id=user_id,
            resource_type=self._resolve_resource_type(agent_type),
            resource_id=self._resolve_resource_id(agent_type),
            action='access',
            consume_trial=False,
        )
        decision = await access_decision_engine.decide(db, ctx)
        if not decision.allowed:
            raise errors.ForbiddenError(msg=self._deny_message(decision))
        return decision

    async def consume_quota(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        agent_type: AgentType,
    ) -> Decision:
        """
        任务成功完成后扣减权益, 失败时不调用以保证不计费

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param agent_type: agent 类型
        :return:
        """
        ctx = AccessContext(
            user_id=user_id,
            resource_type=self._resolve_resource_type(agent_type),
            resource_id=self._resolve_resource_id(agent_type),
            action='access',
            consume_trial=True,
        )
        return await access_decision_engine.decide(db, ctx)

    @staticmethod
    def _resolve_resource_type(agent_type: AgentType) -> str:
        """
        解析 agent 类型对应的 resource_type

        :param agent_type: agent 类型
        :return:
        """
        return AGENT_RESOURCE_TYPE.get(agent_type, 'agents.grading')

    @staticmethod
    def _resolve_resource_id(agent_type: AgentType) -> int:
        """
        解析 agent 类型对应的 resource_id

        :param agent_type: agent 类型
        :return:
        """
        resource_id = AGENT_RESOURCE_IDS.get(agent_type)
        if resource_id is None:
            raise errors.ServerError(msg=f'未配置 agent 类型对应的 resource_id: {agent_type}')
        return resource_id

    @staticmethod
    def _deny_message(decision: Decision) -> str:
        """
        把决策原因码转为用户可读消息

        :param decision: 决策结果
        :return:
        """
        if decision.reason_code == ReasonCode.QUOTA_EXHAUSTED:
            return '今日批改次数已用完, 请明日再来或开通更高权益'
        if decision.reason_code == ReasonCode.NO_MATCHING_GRANT:
            return '当前批改服务需要会员权限'
        if decision.reason_code == ReasonCode.AUDIENCE_NOT_MATCH:
            return '当前权益与用户身份不匹配'
        return '权益校验未通过'


quota_provider: QuotaProvider = QuotaProvider()
