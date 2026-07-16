#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class MyDriveSyncRuleParam(SchemaBase):
    """同步规则参数"""

    sort_order: int = Field(ge=0, description='执行顺序')
    rule_type: str = Field(description='规则类型：exclude 或 rename')
    pattern: str = Field(min_length=1, max_length=1024, description='匹配表达式')
    replacement: str = Field(default='', max_length=1024, description='重命名替换内容')
    is_enabled: bool = Field(default=True, description='是否启用')


class CreateMyDriveSyncRuleSetParam(SchemaBase):
    """创建同步规则集参数"""

    name: str = Field(min_length=1, max_length=128, description='规则集名称')
    description: str = Field(default='', max_length=500, description='规则集描述')
    rules: list[MyDriveSyncRuleParam] = Field(default_factory=list, description='规则列表')


class UpdateMyDriveSyncRuleSetParam(SchemaBase):
    """更新同步规则集参数"""

    name: str | None = Field(default=None, min_length=1, max_length=128, description='规则集名称')
    description: str | None = Field(default=None, max_length=500, description='规则集描述')
    is_enabled: bool | None = Field(default=None, description='是否启用')
    rules: list[MyDriveSyncRuleParam] | None = Field(default=None, description='规则列表')


class GetMyDriveSyncRuleDetail(MyDriveSyncRuleParam):
    """同步规则详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='规则 ID')


class GetMyDriveSyncRuleSetDetail(SchemaBase):
    """同步规则集详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='规则集 ID')
    owner_id: int = Field(description='所属用户 ID')
    name: str = Field(description='规则集名称')
    description: str = Field(description='规则集描述')
    is_enabled: bool = Field(description='是否启用')
    rules: list[GetMyDriveSyncRuleDetail] = Field(default_factory=list, description='规则列表')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')


class GetMyDriveSyncRuleSetListItem(SchemaBase):
    """同步规则集列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='规则集 ID')
    owner_id: int = Field(description='所属用户 ID')
    name: str = Field(description='规则集名称')
    description: str = Field(description='规则集描述')
    is_enabled: bool = Field(description='是否启用')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')


class CreateMyDriveSyncConfigParam(SchemaBase):
    """创建同步配置参数"""

    name: str = Field(min_length=1, max_length=128, description='同步名称')
    source_space_id: int = Field(gt=0, description='源文件空间 ID')
    target_space_id: int = Field(gt=0, description='目标文件空间 ID')
    source_path: str = Field(default='/', min_length=1, max_length=1024, description='源目录路径')
    target_path: str = Field(default='/', min_length=1, max_length=1024, description='目标目录路径')
    rule_set_id: int | None = Field(default=None, gt=0, description='规则集 ID')
    sync_method: str = Field(default='incremental', description='同步模式')
    cron: str | None = Field(default=None, max_length=128, description='定时表达式')
    end_time: datetime | None = Field(default=None, description='配置结束时间')


class UpdateMyDriveSyncConfigParam(SchemaBase):
    """更新同步配置参数"""

    name: str | None = Field(default=None, min_length=1, max_length=128, description='同步名称')
    source_space_id: int | None = Field(default=None, gt=0, description='源文件空间 ID')
    target_space_id: int | None = Field(default=None, gt=0, description='目标文件空间 ID')
    source_path: str | None = Field(default=None, min_length=1, max_length=1024, description='源目录路径')
    target_path: str | None = Field(default=None, min_length=1, max_length=1024, description='目标目录路径')
    rule_set_id: int | None = Field(default=None, gt=0, description='规则集 ID')
    sync_method: str | None = Field(default=None, description='同步模式')
    is_enabled: bool | None = Field(default=None, description='是否启用')
    cron: str | None = Field(default=None, max_length=128, description='定时表达式')
    end_time: datetime | None = Field(default=None, description='配置结束时间')


class GetMyDriveSyncConfigDetail(SchemaBase):
    """同步配置详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='同步配置 ID')
    owner_id: int = Field(description='所属用户 ID')
    name: str = Field(description='同步名称')
    source_space_id: int = Field(description='源文件空间 ID')
    target_space_id: int = Field(description='目标文件空间 ID')
    source_path: str = Field(description='源目录路径')
    target_path: str = Field(description='目标目录路径')
    rule_set_id: int | None = Field(description='规则集 ID')
    sync_method: str = Field(description='同步模式')
    is_enabled: bool = Field(description='是否启用')
    cron: str | None = Field(description='定时表达式')
    end_time: datetime | None = Field(description='配置结束时间')
    last_synced_at: datetime | None = Field(description='最近同步时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')


class GetMyDriveSyncTaskDetail(SchemaBase):
    """同步任务详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='同步任务 ID')
    config_id: int = Field(description='同步配置 ID')
    status: str = Field(description='任务状态')
    cancel_requested: bool = Field(description='是否请求取消')
    statistics: dict = Field(description='任务统计信息')
    error_message: str | None = Field(description='错误信息')
    started_at: datetime | None = Field(description='开始时间')
    finished_at: datetime | None = Field(description='完成时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')


class GetMyDriveSyncTaskItemDetail(SchemaBase):
    """同步任务项详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='同步任务项 ID')
    task_id: int = Field(description='同步任务 ID')
    operation: str = Field(description='操作类型')
    source_path: str = Field(description='源路径')
    target_path: str = Field(description='目标路径')
    file_name: str = Field(description='文件名称')
    file_size: int = Field(description='文件大小')
    status: str = Field(description='执行状态')
    error_message: str | None = Field(description='错误信息')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')
