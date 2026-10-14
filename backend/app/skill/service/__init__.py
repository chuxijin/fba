#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill 业务资源权益定义与会员闸门"""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import ReasonCode, ResourceType
from backend.app.access.schema.engine import Decision
from backend.app.access.service.resource_access_service import resource_access_service
from backend.app.access.service.resource_profile_registry import AccessProfile, access_profile_registry

GONGKAO_SKILL_USE_PROFILE_CODE = 'gongkao.skill.use'
SKILL_KAOGONG_ACCESS_ENTITLEMENT = 'skill.kaogong.access'


def register_skill_access_profiles() -> None:
    """注册 skill 业务权益档案（会员闸门：一码管全部 skill 能力）"""
    profile = AccessProfile(
        code=GONGKAO_SKILL_USE_PROFILE_CODE,
        resource_type=ResourceType.SKILL,
        resource_id=1,
        action='access',
        deny_messages={
            ReasonCode.NO_MATCHING_GRANT: '使用公考 AI 助手需要开通会员',
            ReasonCode.QUOTA_EXHAUSTED: '今日使用次数已用完，请明日再来或开通更高权益',
            ReasonCode.AUDIENCE_NOT_MATCH: '当前权益与用户身份不匹配',
        },
        default_deny_message='使用公考 AI 助手需要开通会员',
    )
    access_profile_registry.register(profile)


register_skill_access_profiles()


async def ensure_skill_access(
    db: AsyncSession,
    *,
    user_id: int,
    raise_on_deny: bool = True,
) -> Decision:
    """skill 业务统一会员闸门（纯准入预检，不扣减任何额度），拒绝时抛 ForbiddenError"""
    return await resource_access_service.decide(
        db,
        profile_code=GONGKAO_SKILL_USE_PROFILE_CODE,
        user_id=user_id,
        consume_trial=False,
        raise_on_deny=raise_on_deny,
    )


async def get_skill_entitlement_status(
    db: AsyncSession,
    *,
    user_id: int,
) -> tuple[bool, str | None]:
    """查询会员资格（不拦截），返回 (can_use, deny_message) 供 CLI 引导"""
    decision = await ensure_skill_access(db, user_id=user_id, raise_on_deny=False)
    if decision.allowed:
        return True, None
    profile = access_profile_registry.get(GONGKAO_SKILL_USE_PROFILE_CODE)
    message = profile.deny_messages.get(decision.reason_code, profile.default_deny_message) if profile else '使用公考 AI 助手需要开通会员'
    return False, message
