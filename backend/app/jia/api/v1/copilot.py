#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.service.copilot_service import copilot_service
from backend.app.jia.crud.crud_copilot import copilot_session_dao, copilot_message_dao
from backend.app.jia.schema.copilot import ChatRequest, ChatResponse, GetSessionListResponse, MessageSchema, AnalyzeItemRequest, AnalyzeItemResponse
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import get_db

router = APIRouter()


@router.post("/chat", summary="发送对话", response_model=ResponseSchemaModel[ChatResponse], dependencies=[DependsJwtAuth])
async def chat(
    req: ChatRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    data = await copilot_service.chat(db, request.user.id, req)
    return response_base.success(data=data)


@router.get("/sessions/{id}/messages", summary="获取会话消息历史", response_model=ResponseSchemaModel[list[MessageSchema]], dependencies=[DependsJwtAuth])
async def get_messages(
    id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    session = await copilot_session_dao.get(db, id)
    if not session:
        return response_base.fail(res=response_base.response_404)

    if session.user_id != request.user.id:
        return response_base.fail(res=response_base.response_403)

    data = await copilot_message_dao.get_all(db, id)
    return response_base.success(data=data)


@router.get("/sessions", summary="获取历史会话列表", response_model=ResponseSchemaModel[list[GetSessionListResponse]], dependencies=[DependsJwtAuth])
async def get_copilot_sessions(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    data = await copilot_session_dao.get_by_user(db, request.user.id)
    return response_base.success(data=data)


@router.post("/analyze-item", summary="智能识别物品", response_model=ResponseSchemaModel[AnalyzeItemResponse], dependencies=[DependsJwtAuth])
async def analyze_item(
    req: AnalyzeItemRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """通过图片或文字描述智能识别物品信息"""
    data = await copilot_service.analyze_item(db, request.user.id, req)
    return response_base.success(data=data)
