#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus
from sqlalchemy import select, desc

from backend.app.jia.model.copilot import JiaCopilotSession, JiaCopilotMessage
from backend.app.jia.schema.copilot import CreateSessionParam, UpdateSessionParam


class CRUDCopilotSession(CRUDPlus[JiaCopilotSession]):
    
    async def create(self, db: AsyncSession, obj: CreateSessionParam, user_id: int) -> JiaCopilotSession:
        return await self.create_model(db, obj, user_id=user_id)
        
    async def get_by_user(self, db: AsyncSession, user_id: int, limit: int = 20):
        """获取用户的最近会话"""
        stmt = select(JiaCopilotSession).where(
            JiaCopilotSession.user_id == user_id
        ).order_by(desc(JiaCopilotSession.updated_time)).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()


class CRUDCopilotMessage(CRUDPlus[JiaCopilotMessage]):
    
    async def get_history(self, db: AsyncSession, session_id: int, limit: int = 20):
        """获取会话历史消息 (按时间正序)"""
        # 先倒序取最近N条，再正序排列
        stmt = select(JiaCopilotMessage).where(
            JiaCopilotMessage.session_id == session_id
        ).order_by(desc(JiaCopilotMessage.created_time)).limit(limit)
        
        result = await db.execute(stmt)
        messages = result.scalars().all()
        # Sort explicitly in Python to ensure order if limit was applied on desc
        return sorted(messages, key=lambda x: x.created_time)

    async def get_all(self, db: AsyncSession, session_id: int):
        """获取所有会话历史消息 (按时间正序)"""
        stmt = select(JiaCopilotMessage).where(
            JiaCopilotMessage.session_id == session_id
        ).order_by(JiaCopilotMessage.created_time)
        
        result = await db.execute(stmt)
        return result.scalars().all()


copilot_session_dao = CRUDCopilotSession(JiaCopilotSession)
copilot_message_dao = CRUDCopilotMessage(JiaCopilotMessage)
