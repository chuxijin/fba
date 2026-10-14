#!/usr/bin/env python3
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from backend.app.payment.model.group_buy import PayGroupBuyMember, PayGroupBuyTask, PayGroupBuyTeam
from backend.app.payment.schema.group_buy import (
    GroupBuyActivityParam,
    GroupBuyCreateTeamParam,
    GroupBuyPrepayParam,
    GroupBuyTaskRetryParam,
)
from backend.app.payment.schema.pay import SubscriptionPrepayResult
from backend.app.payment.service.group_buy_service import group_buy_service
from backend.common.exception import errors
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction, async_db_session
from backend.utils.timezone import timezone

router = APIRouter(prefix='/group-buy', tags=['订阅拼团'])


@router.get('/activities', summary='可售拼团活动')
async def activities(db: CurrentSession) -> ResponseModel:
    return response_base.success(data=await group_buy_service.activities(db))


@router.get('/activities/{activity_id}', summary='可售拼团活动详情')
async def activity_detail(db: CurrentSession, activity_id: int) -> ResponseModel:
    activity = next((a for a in await group_buy_service.activities(db) if a['id'] == activity_id), None)
    if not activity:
        raise errors.NotFoundError(msg='可售活动不存在')
    return response_base.success(data=activity)


@router.get(
    '/admin/activities',
    summary='拼团活动管理列表',
    dependencies=[Depends(RequestPermission('payment:group-buy:list')), DependsRBAC],
)
async def admin_activities(db: CurrentSession) -> ResponseModel:
    return response_base.success(data=await group_buy_service.activities(db, admin=True))


@router.post(
    '/admin/activities',
    summary='配置拼团活动',
    dependencies=[Depends(RequestPermission('payment:group-buy:create')), DependsRBAC],
)
async def create_activity(request: Request, db: CurrentSessionTransaction, obj: GroupBuyActivityParam) -> ResponseModel:
    return response_base.success(data={'id': await group_buy_service.configure(db, obj=obj, user_id=request.user.id)})


@router.put(
    '/admin/activities/{activity_id}',
    summary='更新拼团活动',
    dependencies=[Depends(RequestPermission('payment:group-buy:update')), DependsRBAC],
)
async def update_activity(
    request: Request, db: CurrentSessionTransaction, activity_id: int, obj: GroupBuyActivityParam
) -> ResponseModel:
    return response_base.success(
        data={'id': await group_buy_service.configure(db, obj=obj, user_id=request.user.id, activity_id=activity_id)}
    )


@router.get(
    '/admin/tasks',
    summary='拼团交易补偿任务',
    dependencies=[Depends(RequestPermission('payment:group-buy:list')), DependsRBAC],
)
async def admin_tasks(db: CurrentSession, status: str | None = None) -> ResponseModel:
    stmt = select(PayGroupBuyTask).order_by(PayGroupBuyTask.id.desc()).limit(100)
    if status:
        stmt = stmt.where(PayGroupBuyTask.status == status)
    rows = (await db.scalars(stmt)).all()
    return response_base.success(
        data=[
            {
                'id': t.id,
                'key': t.key,
                'kind': t.kind,
                'status': t.status,
                'order_id': t.order_id,
                'team_id': t.team_id,
                'attempts': t.attempts,
                'error': t.error,
                'refund_no': t.payload.get('refund_no'),
                'available_at': t.available_at,
            }
            for t in rows
        ]
    )


@router.post(
    '/admin/tasks/{task_id}/retry',
    summary='重试拼团失败任务',
    dependencies=[Depends(RequestPermission('payment:group-buy:update')), DependsRBAC],
)
async def retry_task(
    request: Request, db: CurrentSessionTransaction, task_id: int, obj: GroupBuyTaskRetryParam
) -> ResponseModel:
    task = (
        await db.scalars(select(PayGroupBuyTask).where(PayGroupBuyTask.id == task_id).with_for_update())
    ).one_or_none()
    if not task or task.status not in ('failed', 'manual_review'):
        raise errors.RequestError(msg='只有失败或待核实任务可重试')
    if task.kind == 'refund' and task.payload.get('dispatch_started'):
        if not obj.confirmed_not_sent or (
            task.payload.get('refund_accepted') and not task.payload.get('channel_failed')
        ):
            raise errors.RequestError(msg='退款已派发；必须先核实渠道未受理，已受理退款不能重新提交')
        task.payload = {
            **task.payload,
            'dispatch_started': False,
            'verified_not_sent_by': request.user.id,
            'verified_not_sent_at': timezone.now().isoformat(),
        }
    task.status, task.error, task.attempts = 'pending', None, 0
    task.available_at, task.lease_until = timezone.now(), None
    return response_base.success()


@router.post('/teams', summary='创建团长待付款拼团', dependencies=[DependsJwtAuth])
async def create_team(request: Request, db: CurrentSessionTransaction, obj: GroupBuyCreateTeamParam) -> ResponseModel:
    team = await group_buy_service.create_team(db, user_id=request.user.id, obj=obj)
    return response_base.success(data=await group_buy_service.detail(db, team.share_code, user_id=request.user.id))


@router.get('/teams/my', summary='我的拼团', dependencies=[DependsJwtAuth])
async def my_teams(request: Request, db: CurrentSession) -> ResponseModel:
    codes = (
        await db.scalars(
            select(PayGroupBuyTeam.share_code)
            .join(PayGroupBuyMember, PayGroupBuyMember.team_id == PayGroupBuyTeam.id)
            .where(PayGroupBuyMember.user_id == request.user.id)
            .order_by(PayGroupBuyTeam.id.desc())
            .limit(50)
        )
    ).all()
    return response_base.success(
        data=[await group_buy_service.detail(db, code, user_id=request.user.id) for code in codes]
    )


@router.get('/teams/open', summary='可参与的进行中团（脱敏）')
async def open_teams(db: CurrentSession, limit: Annotated[int, Query(ge=1, le=50)] = 20) -> ResponseModel:
    return response_base.success(data=await group_buy_service.open_teams(db, limit=limit))


@router.get('/teams/{share_code}', summary='脱敏拼团详情')
async def public_team(db: CurrentSession, share_code: str) -> ResponseModel:
    return response_base.success(data=await group_buy_service.detail(db, share_code))


@router.get('/teams/{share_code}/mine', summary='拼团详情及本人订单', dependencies=[DependsJwtAuth])
async def own_team(request: Request, db: CurrentSession, share_code: str) -> ResponseModel:
    return response_base.success(data=await group_buy_service.detail(db, share_code, user_id=request.user.id))


@router.get('/teams/{share_code}/qrcode', summary='获取本人已参与团的邀请小程序码', dependencies=[DependsJwtAuth])
async def team_qrcode(request: Request, db: CurrentSession, share_code: str) -> ResponseModel:
    from backend.app.payment.service.group_buy_share_service import group_buy_share_service

    return response_base.success(
        data=await group_buy_share_service.qrcode(db, code=share_code, user_id=request.user.id)
    )


@router.post('/teams/{share_code}/prepay', summary='本人占位并按快照团价支付', dependencies=[DependsJwtAuth])
async def prepay(
    request: Request, share_code: str, obj: GroupBuyPrepayParam
) -> ResponseSchemaModel[SubscriptionPrepayResult]:
    # 必须先提交占位及业务订单，再调用渠道。网络失败仍有可恢复、可查证的订单。
    async with async_db_session.begin() as db:
        order = await group_buy_service.reserve_order(db, code=share_code, user_id=request.user.id, obj=obj)
        order_id = order.id
    result = await group_buy_service.prepay(order_id=order_id, user_id=request.user.id, obj=obj)
    return response_base.success(data=result)
