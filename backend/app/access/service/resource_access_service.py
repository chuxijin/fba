#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.crud.crud_ledger import quota_ledger_dao
from backend.app.access.engine.decide import access_decision_engine
from backend.app.access.engine.ledger import ledger_service
from backend.app.access.schema.engine import AccessContext, Decision
from backend.app.access.service.resource_profile_registry import AccessProfile, access_profile_registry
from backend.common.exception import errors

import backend.app.access.service.resource_profiles  # noqa: F401


class ResourceAccessService:
    """通用资源权益服务"""

    @staticmethod
    def register_profile(profile: AccessProfile) -> AccessProfile:
        """
        注册资源权益档案

        :param profile: 资源权益档案
        :return:
        """
        return access_profile_registry.register(profile)

    @staticmethod
    def get_profile(*, profile_code: str) -> AccessProfile:
        """
        获取资源权益档案

        :param profile_code: 档案编码
        :return:
        """
        profile = access_profile_registry.get(profile_code)
        if profile is None:
            raise errors.ServerError(msg=f'未注册资源权益档案: {profile_code}')
        return profile

    async def ensure(
        self,
        db: AsyncSession,
        *,
        profile_code: str,
        user_id: int,
        request_ts: datetime | None = None,
        audience_attrs: dict[str, Any] | None = None,
    ) -> Decision:
        """
        资源准入预检，不扣减

        :param db: 数据库会话
        :param profile_code: 档案编码
        :param user_id: 用户 ID
        :param request_ts: 请求时间
        :param audience_attrs: 受众画像
        :return:
        """
        return await self.decide(
            db,
            profile_code=profile_code,
            user_id=user_id,
            consume_trial=False,
            request_ts=request_ts,
            audience_attrs=audience_attrs,
            raise_on_deny=True,
        )

    async def consume(
        self,
        db: AsyncSession,
        *,
        profile_code: str,
        user_id: int,
        source_ref: str | None = None,
        request_ts: datetime | None = None,
        audience_attrs: dict[str, Any] | None = None,
        raise_on_deny: bool = True,
    ) -> Decision:
        """
        资源消耗决策

        :param db: 数据库会话
        :param profile_code: 档案编码
        :param user_id: 用户 ID
        :param source_ref: 来源引用
        :param request_ts: 请求时间
        :param audience_attrs: 受众画像
        :param raise_on_deny: 拒绝时是否抛异常
        :return:
        """
        return await self.decide(
            db,
            profile_code=profile_code,
            user_id=user_id,
            consume_trial=True,
            source_ref=source_ref,
            request_ts=request_ts,
            audience_attrs=audience_attrs,
            raise_on_deny=raise_on_deny,
        )

    async def decide(
        self,
        db: AsyncSession,
        *,
        profile_code: str,
        user_id: int,
        consume_trial: bool,
        source_ref: str | None = None,
        request_ts: datetime | None = None,
        audience_attrs: dict[str, Any] | None = None,
        raise_on_deny: bool = False,
    ) -> Decision:
        """
        按资源档案执行权益决策

        :param db: 数据库会话
        :param profile_code: 档案编码
        :param user_id: 用户 ID
        :param consume_trial: 是否允许扣减
        :param source_ref: 来源引用
        :param request_ts: 请求时间
        :param audience_attrs: 受众画像
        :param raise_on_deny: 拒绝时是否抛异常
        :return:
        """
        profile = self.get_profile(profile_code=profile_code)
        ctx = AccessContext(
            user_id=user_id,
            resource_type=profile.resource_type,
            resource_id=profile.resource_id,
            action=profile.action,
            consume_trial=consume_trial,
            scope_key=profile.scope_key,
            source_ref=source_ref,
            request_ts=request_ts,
            audience_attrs=audience_attrs or {},
        )
        decision = await access_decision_engine.decide(db, ctx)
        if raise_on_deny and not decision.allowed:
            raise errors.ForbiddenError(msg=self._deny_message(profile, decision))
        return decision

    async def refund(
        self,
        db: AsyncSession,
        *,
        profile_code: str,
        user_id: int,
        decision: Decision,
        source_ref: str | None = None,
    ) -> None:
        """
        回滚已扣减配额

        :param db: 数据库会话
        :param profile_code: 档案编码
        :param user_id: 用户 ID
        :param decision: 消耗决策
        :param source_ref: 来源引用
        :return:
        """
        if decision.consumed_ledger_id is None:
            return

        profile = self.get_profile(profile_code=profile_code)
        entry = await quota_ledger_dao.select_model(db, decision.consumed_ledger_id)
        if entry is None:
            return

        await ledger_service.refund(
            db,
            user_id=user_id,
            entitlement_code=entry.entitlement_code,
            amount=entry.amount,
            cycle_type=entry.cycle_type,
            cycle_key=entry.cycle_key,
            scope_key=entry.scope_key,
            source='trial_refund',
            source_ref=source_ref or f'{profile.code}:refund:{entry.id}',
            idempotency_key=f'refund:{entry.id}',
            reason=profile.refund_reason,
        )

    @staticmethod
    def _deny_message(profile: AccessProfile, decision: Decision) -> str:
        """
        解析拒绝提示

        :param profile: 资源权益档案
        :param decision: 权益决策
        :return:
        """
        return profile.deny_messages.get(decision.reason_code, profile.default_deny_message)


resource_access_service: ResourceAccessService = ResourceAccessService()
