#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request

from backend.app.access.engine.decide import access_decision_engine
from backend.app.access.engine.resolver import rule_resolver
from backend.app.access.engine.snapshot import snapshot_service
from backend.app.access.schema.debug import AccessDebugParam
from backend.app.access.schema.engine import AccessContext
from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.utils.timezone import timezone

router = APIRouter()


def _normalize_resource_type(resource_type: str) -> str:
    """
    归一化调试资源类型

    :param resource_type: 前端资源类型
    :return:
    """
    if resource_type in {'qbank.bank', 'question_bank', 'study_question_bank'}:
        return 'qbank'
    return resource_type


@router.post('/debug', summary='调试权益决策', dependencies=[DependsJwtAuth])
async def debug_access_decision(
    request: Request,
    db: CurrentSession,
    obj: AccessDebugParam,
) -> ResponseModel:
    """
    调试权益决策

    :param request: 请求对象
    :param db: 数据库会话
    :param obj: 调试参数
    :return:
    """
    request_ts = timezone.now()
    user_id = obj.user_id or request.user.id
    resource_type = _normalize_resource_type(obj.resource_type)
    ctx = AccessContext(
        user_id=user_id,
        resource_type=resource_type,
        resource_id=obj.resource_id,
        action=obj.action,
        consume_trial=False,
        request_ts=request_ts,
        audience_attrs=obj.audience_attrs,
    )
    rules = await rule_resolver.resolve(
        db,
        resource_type=ctx.resource_type,
        resource_id=ctx.resource_id,
        ts=request_ts,
        audience_attrs=ctx.audience_attrs,
    )
    snapshot = await snapshot_service.load(db, user_id=user_id, ts=request_ts)
    decision = await access_decision_engine.decide(db, ctx)

    return response_base.success(
        data={
            'decision': decision.model_dump(mode='json'),
            'rules': [
                {
                    'id': rule.id,
                    'resource_type': rule.resource_type,
                    'resource_id': rule.resource_id,
                    'entitlement_code': rule.entitlement_code,
                    'grant_mode': rule.grant_mode,
                    'priority': rule.priority,
                    'trial_policy': rule.trial_policy,
                    'inherit_to_children': rule.inherit_to_children,
                }
                for rule in rules
            ],
            'snapshot': snapshot_service.to_audit_dict(snapshot),
        }
    )
