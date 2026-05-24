#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.common.exception import errors
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.plugin.webhook.crud.crud_event_log import crud_event_log
from backend.plugin.webhook.schema.inbound import EventLogListParam, GetEventLogDetail

router = APIRouter()


@router.get(
    '',
    summary='分页获取入站事件日志',
    dependencies=[
        DependsJwtAuth,
        DependsPagination,
    ],
)
async def list_event_logs(
    db: CurrentSession,
    source: Annotated[str | None, Query(description='事件来源')] = None,
    event_type: Annotated[str | None, Query(description='事件类型')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
    start_time: Annotated[str | None, Query(description='开始时间')] = None,
    end_time: Annotated[str | None, Query(description='结束时间')] = None,
) -> ResponseSchemaModel[PageData[GetEventLogDetail]]:
    """分页获取入站事件日志列表"""
    params = EventLogListParam(
        source=source,
        event_type=event_type,
        status=status,
        start_time=start_time,
        end_time=end_time,
    )
    select = await crud_event_log.get_list(params)
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取入站事件日志详情', dependencies=[DependsJwtAuth])
async def get_event_log(pk: Annotated[int, Path(description='日志 ID')]) -> ResponseSchemaModel[GetEventLogDetail]:
    """获取入站事件日志详情"""
    event_log = await crud_event_log.get(None, pk)
    if not event_log:
        raise errors.NotFoundError(msg='事件日志不存在')
    return response_base.success(data=GetEventLogDetail.model_validate(event_log))
