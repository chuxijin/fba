#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class BiliTaskConfigBase(SchemaBase):
    task_name: str = Field(description='任务名称')
    task_type: str = Field(description='任务类型: reply_my_message/reply_my_comment/send_to_others_comment')
    is_enabled: bool = Field(default=True, description='是否启用')

    # 时间配置
    start_time: str = Field(description='开始时间 HH:MM:SS')
    end_time: str = Field(description='结束时间 HH:MM:SS')
    rest_start_time: str | None = Field(default=None, description='休息开始时间')
    rest_end_time: str | None = Field(default=None, description='休息结束时间')
    check_interval_min: int = Field(default=30, description='检查间隔最小值（秒）')
    check_interval_max: int = Field(default=60, description='检查间隔最大值（秒）')

    # 关联配置
    account_id: int = Field(description='执行账号 ID')
    work_id: int | None = Field(default=None, description='关联作品 ID')
    template_ids: str | None = Field(default=None, description='关联模板 ID 列表（JSON）')

    # 筛选条件
    filter_config: str | None = Field(default=None, description='筛选条件配置（JSON）')
    description: str | None = Field(default=None, description='任务描述')


class CreateBiliTaskConfig(BiliTaskConfigBase):
    """创建任务配置"""

    pass


class UpdateBiliTaskConfig(SchemaBase):
    """更新任务配置"""

    task_name: str | None = Field(default=None, description='任务名称')
    task_type: str | None = Field(
        default=None, description='任务类型: reply_my_message/reply_my_comment/send_to_others_comment'
    )
    is_enabled: bool | None = Field(default=None, description='是否启用')

    # 时间配置
    start_time: str | None = Field(default=None, description='开始时间 HH:MM:SS')
    end_time: str | None = Field(default=None, description='结束时间 HH:MM:SS')
    rest_start_time: str | None = Field(default=None, description='休息开始时间')
    rest_end_time: str | None = Field(default=None, description='休息结束时间')
    check_interval_min: int | None = Field(default=None, description='检查间隔最小值（秒）')
    check_interval_max: int | None = Field(default=None, description='检查间隔最大值（秒）')

    # 关联配置
    account_id: int | None = Field(default=None, description='执行账号 ID')
    work_id: int | None = Field(default=None, description='关联作品 ID')
    template_ids: str | None = Field(default=None, description='关联模板 ID 列表（JSON）')

    # 筛选条件
    filter_config: str | None = Field(default=None, description='筛选条件配置（JSON）')
    description: str | None = Field(default=None, description='任务描述')


class GetBiliTaskConfigDetail(BiliTaskConfigBase):
    """任务配置详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_first_run: bool
    last_processed_id: str | None = None
    last_processed_time: datetime | None = None
    last_run_time: datetime | None = None
    last_check_time: datetime | None = None
    next_run_time: datetime | None = None
    run_count: int
    reply_count: int
    send_count: int
    fail_count: int
    last_error: str | None = None
    created_time: datetime
    updated_time: datetime | None = None
