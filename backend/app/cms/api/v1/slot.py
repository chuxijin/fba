#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.cms.schema.slot import GetActiveSlot, ReportSlotActionParam
from backend.app.cms.service.slot_service import slot_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

router = APIRouter(prefix='/cms', tags=['内容运营位'])


@router.get('/slots/active', summary='获取场景下命中的运营位列表')
async def get_active_slots(
    request: Request,
    db: CurrentSession,
    scene: Annotated[str, Query(min_length=1, max_length=64, description='触发场景')],
) -> ResponseSchemaModel[list[GetActiveSlot]]:
    """获取场景下命中的运营位列表(支持未登录, 未登录跳过分群与频次校验)"""
    user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') else None
    data = await slot_service.get_active_slots(db=db, scene=scene, user_id=user_id)
    return response_base.success(data=data)


@router.post('/slots/{pk}/log', summary='上报运营位行为')
async def report_action(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='运营位 ID')],
    obj: ReportSlotActionParam,
) -> ResponseModel:
    """上报运营位行为(0 曝光 1 点击 2 关闭)"""
    user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') else None
    await slot_service.report_action(
        db=db, slot_id=pk, user_id=user_id, action=obj.action, scene=obj.scene
    )
    return response_base.success()
