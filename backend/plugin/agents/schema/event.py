#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase
from backend.plugin.agents.schema.report import AgentType, SectionName


class EventType(StrEnum):
    """SSE 事件类型"""

    stage_start = 'stage_start'
    stage_finish = 'stage_finish'
    section_ready = 'section_ready'
    intermediate_text = 'intermediate_text'
    progress = 'progress'
    completed = 'completed'
    failed = 'failed'


class AgentEvent(SchemaBase):
    """SSE 推送事件"""

    event_type: EventType = Field(description='事件类型')
    task_id: int = Field(description='任务 ID')
    agent_type: AgentType = Field(description='agent 类型')
    stage: str = Field(default='', description='当前阶段标识')
    progress: float = Field(default=0.0, description='整体进度 0-1')
    section_name: SectionName | None = Field(default=None, description='本次推送的 section')
    section_data: dict[str, Any] | None = Field(default=None, description='section 内容')
    text_delta: str | None = Field(default=None, description='增量文本')
    message: str = Field(default='', description='人类可读消息')
    error_code: str | None = Field(default=None, description='错误码')
    timestamp: datetime = Field(default_factory=datetime.now, description='时间戳')
