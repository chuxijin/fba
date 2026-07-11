#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.access.constants import ReasonCode, ResourceType
from backend.app.access.service.resource_profile_registry import AccessProfile, access_profile_registry

RENDER_BOOK_EXPORT_PROFILE_CODE = 'render_book.export'
AGENT_SHENLUN_GRADE_PROFILE_CODE = 'agent.shenlun.grade'
AGENT_ENGLISH_ESSAY_GRADE_PROFILE_CODE = 'agent.english_essay.grade'
AGENT_XINGCE_GRADE_PROFILE_CODE = 'agent.xingce.grade'
AGENT_INTERVIEW_GRADE_PROFILE_CODE = 'agent.interview.grade'


def register_builtin_access_profiles() -> None:
    """注册内置资源权益档案"""
    shared_agent_messages = {
        ReasonCode.QUOTA_EXHAUSTED: '今日批改次数已用完, 请明日再来或开通更高权益',
        ReasonCode.NO_MATCHING_GRANT: '当前批改服务需要会员权限',
        ReasonCode.AUDIENCE_NOT_MATCH: '当前权益与用户身份不匹配',
    }

    profiles = (
        AccessProfile(
            code=RENDER_BOOK_EXPORT_PROFILE_CODE,
            resource_type=ResourceType.RENDER_BOOK,
            resource_id=1,
            action='export',
            scope_key='render_book',
            deny_messages={
                ReasonCode.QUOTA_EXHAUSTED: '今日 PDF 生成次数已用完，请明日再来或获取更多配额',
                ReasonCode.NO_MATCHING_GRANT: '当前用户没有题本导出配额',
                ReasonCode.AUDIENCE_NOT_MATCH: '当前 PDF 导出配额与用户身份不匹配',
            },
            refund_reason='render book generation failed',
        ),
        AccessProfile(
            code=AGENT_SHENLUN_GRADE_PROFILE_CODE,
            resource_type=ResourceType.AGENT_SHENLUN,
            resource_id=1,
            action='access',
            deny_messages=shared_agent_messages,
            refund_reason='agent grading failed',
        ),
        AccessProfile(
            code=AGENT_ENGLISH_ESSAY_GRADE_PROFILE_CODE,
            resource_type='agents.grading',
            resource_id=2,
            action='access',
            deny_messages=shared_agent_messages,
            refund_reason='agent grading failed',
        ),
        AccessProfile(
            code=AGENT_XINGCE_GRADE_PROFILE_CODE,
            resource_type='agents.grading',
            resource_id=3,
            action='access',
            deny_messages=shared_agent_messages,
            refund_reason='agent grading failed',
        ),
        AccessProfile(
            code=AGENT_INTERVIEW_GRADE_PROFILE_CODE,
            resource_type='agents.grading',
            resource_id=4,
            action='access',
            deny_messages=shared_agent_messages,
            refund_reason='agent grading failed',
        ),
    )
    for profile in profiles:
        access_profile_registry.register(profile)


register_builtin_access_profiles()
