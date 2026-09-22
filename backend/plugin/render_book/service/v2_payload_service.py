#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V2 Render Payload Service 别名兼容模块。

为了保持向前向后兼容性，将 V2RenderPayloadService 重定向至统一的 RenderPayloadService。
"""
from backend.plugin.render_book.service.payload_service import (
    QUESTION_TYPE_LABELS,
    RenderPayloadService,
    render_payload_service,
)

V2RenderPayloadService = RenderPayloadService
v2_render_payload_service = render_payload_service

__all__ = [
    'QUESTION_TYPE_LABELS',
    'RenderPayloadService',
    'V2RenderPayloadService',
    'render_payload_service',
    'v2_render_payload_service',
]
