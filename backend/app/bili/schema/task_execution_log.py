#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict

from backend.common.schema import SchemaBase


class GetBiliTaskExecutionLogDetail(SchemaBase):
    """任务执行记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_config_id: int
    task_name: str
    task_type: str

    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: int | None = None

    comments_fetched: int
    users_processed: int
    users_skipped: int
    send_success: int
    send_fail: int

    execution_status: str
    error_message: str | None = None

    work_id: int | None = None
    account_id: int | None = None

    created_time: datetime
