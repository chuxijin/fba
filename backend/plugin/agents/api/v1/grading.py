#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from starlette.responses import StreamingResponse

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.agents.schema import GradingDetail, GradingOcrResult, GradingStartParam, GradingStartResult
from backend.plugin.agents.service.common.streaming import event_bus, sse_stream
from backend.plugin.agents.service.grading_service import grading_service

router = APIRouter()


@router.post('/start', summary='启动批改任务')
async def start_grading(
    db: CurrentSessionTransaction,
    obj: GradingStartParam,
) -> ResponseSchemaModel[GradingStartResult]:
    """
    启动批改任务, 立即返回 task_id 与 SSE 订阅地址

    :param db: 数据库会话
    :param obj: 启动参数
    :return:
    """
    result = await grading_service.start(db=db, params=obj)
    return response_base.success(data=result)


@router.post('/ocr', summary='OCR 识别考生答卷图片')
async def recognize_grading_answer(
    files: Annotated[list[UploadFile], File(description='考生答卷图片, 支持多张')],
    provider: Annotated[str | None, Form(description='OCR provider, 留空走默认配置')] = None,
) -> ResponseSchemaModel[GradingOcrResult]:
    """
    上传考生答卷图片, 调 OCR 返回归一化后的纯文本, 前端拿到 text 后再调 /start 启动批改

    :param files: 上传的图片
    :param provider: OCR provider 名称
    :return:
    """
    result = await grading_service.recognize_user_answer(files=files, provider=provider)
    return response_base.success(data=result)


@router.get('/{task_id}/stream', summary='订阅批改 SSE 事件流')
async def stream_grading(task_id: int) -> StreamingResponse:
    """
    订阅指定批改任务的 SSE 事件流

    :param task_id: 任务 ID
    :return:
    """
    return StreamingResponse(
        sse_stream(event_bus, task_id),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


@router.get('/{task_id}', summary='获取批改详情')
async def get_grading(
    db: CurrentSession,
    task_id: int,
) -> ResponseSchemaModel[GradingDetail]:
    """
    获取批改任务详情

    :param db: 数据库会话
    :param task_id: 任务 ID
    :return:
    """
    detail = await grading_service.get_detail(db=db, task_id=task_id)
    return response_base.success(data=detail)
