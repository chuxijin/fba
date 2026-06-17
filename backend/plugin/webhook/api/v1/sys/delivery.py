#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.plugin.webhook.crud.crud_delivery import crud_delivery
from backend.plugin.webhook.schema.delivery import DeliveryListParam, GetDeliveryDetail
from backend.plugin.webhook.service.delivery_service import delivery_service

router = APIRouter()


@router.get(
    '',
    summary='分页获取投递记录',
    dependencies=[
        DependsJwtAuth,
        DependsPagination,
    ],
)
async def list_deliveries(
    db: CurrentSession,
    endpoint_id: Annotated[int | None, Query(description='端点 ID')] = None,
    event_type: Annotated[str | None, Query(description='事件类型')] = None,
    status: Annotated[int | None, Query(description='投递状态')] = None,
    start_time: Annotated[str | None, Query(description='开始时间')] = None,
    end_time: Annotated[str | None, Query(description='结束时间')] = None,
) -> ResponseSchemaModel[PageData[GetDeliveryDetail]]:
    """分页获取投递记录列表"""
    params = DeliveryListParam(
        endpoint_id=endpoint_id,
        event_type=event_type,
        status=status,
        start_time=start_time,
        end_time=end_time,
    )
    select = await crud_delivery.get_list(params)
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取投递记录详情', dependencies=[DependsJwtAuth])
async def get_delivery(pk: Annotated[int, Path(description='投递记录 ID')]) -> ResponseSchemaModel[GetDeliveryDetail]:
    """获取投递记录详情"""
    from backend.common.exception import errors
    from backend.database.db import async_db_session

    async with async_db_session() as db:
        delivery = await crud_delivery.get(db, pk)
    if not delivery:
        raise errors.NotFoundError(msg='投递记录不存在')
    return response_base.success(data=GetDeliveryDetail.model_validate(delivery))


@router.post(
    '/{pk}/retry',
    summary='手动重试投递',
    dependencies=[DependsJwtAuth],
)
async def retry_delivery(pk: Annotated[int, Path(description='投递记录 ID')]) -> ResponseModel:
    """手动重试一条失败的投递记录"""
    from backend.plugin.webhook.constant import DeliveryStatus
    from backend.plugin.webhook.model.webhook_delivery import WebhookDelivery
    from backend.database.db import async_db_session
    from sqlalchemy import update

    async with async_db_session.begin() as db:
        stmt = (
            update(WebhookDelivery)
            .where(WebhookDelivery.id == pk)
            .values(status=DeliveryStatus.PENDING, attempt_count=0, next_retry_at=None)
        )
        result = await db.execute(stmt)

    if result.rowcount > 0:
        return response_base.success(data={'message': '已重置为待投递状态'})
    return response_base.fail()


@router.post(
    '/process',
    summary='手动触发投递处理',
    dependencies=[DependsJwtAuth],
)
async def process_pending(batch_size: Annotated[int, Query(ge=1, le=200)] = 50) -> ResponseSchemaModel[dict[str, Any]]:
    """手动触发处理待投递的记录"""
    processed = await delivery_service.process_pending(batch_size=batch_size)
    return response_base.success(data={'processed': processed, 'message': f'已处理 {processed} 条投递记录'})
