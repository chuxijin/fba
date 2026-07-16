#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.mydrive.model.account import CompatibleJSONB
from backend.common.model import Base, TimeZone, id_key


class MyDriveSyncRuleSet(Base):
    """文件同步规则集表"""

    __tablename__ = 'mydrive_sync_rule_set'
    __table_args__ = (
        sa.UniqueConstraint('owner_id', 'name', name='uq_mydrive_sync_rule_set_owner_name'),
        sa.Index('idx_mydrive_sync_rule_set_owner_enabled', 'owner_id', 'is_enabled'),
        {'comment': '文件同步规则集表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    owner_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='所属用户 ID')
    name: Mapped[str] = mapped_column(sa.String(128), comment='规则集名称')
    description: Mapped[str] = mapped_column(sa.String(500), default='', comment='规则集描述')
    is_enabled: Mapped[bool] = mapped_column(default=True, comment='是否启用')


class MyDriveSyncRule(Base):
    """文件同步规则表"""

    __tablename__ = 'mydrive_sync_rule'
    __table_args__ = (
        sa.UniqueConstraint('rule_set_id', 'sort_order', name='uq_mydrive_sync_rule_order'),
        sa.Index('idx_mydrive_sync_rule_set_enabled', 'rule_set_id', 'is_enabled'),
        sa.CheckConstraint("rule_type IN ('exclude','rename')", name='ck_mydrive_sync_rule_type'),
        {'comment': '文件同步规则表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    rule_set_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mydrive_sync_rule_set.id', ondelete='CASCADE'),
        comment='规则集 ID',
    )
    sort_order: Mapped[int] = mapped_column(sa.Integer, comment='执行顺序')
    rule_type: Mapped[str] = mapped_column(sa.String(16), comment='规则类型')
    pattern: Mapped[str] = mapped_column(sa.String(1024), comment='匹配表达式')
    replacement: Mapped[str] = mapped_column(sa.String(1024), default='', comment='重命名替换内容')
    is_enabled: Mapped[bool] = mapped_column(default=True, comment='是否启用')


class MyDriveSyncConfig(Base):
    """文件同步配置表"""

    __tablename__ = 'mydrive_sync_config'
    __table_args__ = (
        sa.Index('idx_mydrive_sync_config_owner_enabled', 'owner_id', 'is_enabled'),
        sa.Index('idx_mydrive_sync_config_source_target', 'source_space_id', 'target_space_id'),
        sa.CheckConstraint("sync_method IN ('incremental','full','overwrite')", name='ck_mydrive_sync_config_method'),
        {'comment': '文件同步配置表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    owner_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='所属用户 ID')
    name: Mapped[str] = mapped_column(sa.String(128), comment='同步名称')
    source_space_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mydrive_space.id', ondelete='CASCADE'),
        comment='源文件空间 ID',
    )
    target_space_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mydrive_space.id', ondelete='CASCADE'),
        comment='目标文件空间 ID',
    )
    source_path: Mapped[str] = mapped_column(sa.String(1024), default='/', comment='源目录路径')
    target_path: Mapped[str] = mapped_column(sa.String(1024), default='/', comment='目标目录路径')
    rule_set_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mydrive_sync_rule_set.id', ondelete='SET NULL'),
        default=None,
        comment='规则集 ID',
    )
    sync_method: Mapped[str] = mapped_column(
        sa.String(16), default='incremental', comment='同步模式'
    )
    is_enabled: Mapped[bool] = mapped_column(default=True, comment='是否启用')
    cron: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='定时表达式')
    end_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='配置结束时间')
    last_synced_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近同步时间')


class MyDriveSyncTask(Base):
    """文件同步任务表"""

    __tablename__ = 'mydrive_sync_task'
    __table_args__ = (
        sa.Index('idx_mydrive_sync_task_config_status', 'config_id', 'status'),
        sa.CheckConstraint("status IN ('pending','running','completed','failed','cancelled')", name='ck_mydrive_sync_task_status'),
        {'comment': '文件同步任务表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    config_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mydrive_sync_config.id', ondelete='CASCADE'),
        comment='同步配置 ID',
    )
    status: Mapped[str] = mapped_column(sa.String(16), default='pending', comment='任务状态')
    cancel_requested: Mapped[bool] = mapped_column(default=False, comment='是否请求取消')
    statistics: Mapped[dict] = mapped_column(CompatibleJSONB, default_factory=dict, comment='任务统计信息')
    error_message: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='错误信息')
    started_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='开始时间')
    finished_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='完成时间')


class MyDriveSyncTaskItem(Base):
    """文件同步任务项表"""

    __tablename__ = 'mydrive_sync_task_item'
    __table_args__ = (
        sa.Index('idx_mydrive_sync_task_item_task_status', 'task_id', 'status'),
        sa.CheckConstraint(
            "operation IN ('copy','transfer','create_directory','rename','remove','skip')",
            name='ck_mydrive_sync_task_item_operation',
        ),
        {'comment': '文件同步任务项表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    task_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mydrive_sync_task.id', ondelete='CASCADE'),
        comment='同步任务 ID',
    )
    operation: Mapped[str] = mapped_column(sa.String(32), comment='操作类型')
    source_path: Mapped[str] = mapped_column(sa.String(1024), comment='源路径')
    target_path: Mapped[str] = mapped_column(sa.String(1024), comment='目标路径')
    file_name: Mapped[str] = mapped_column(sa.String(512), comment='文件名称')
    file_size: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='文件大小')
    status: Mapped[str] = mapped_column(sa.String(16), default='pending', comment='执行状态')
    error_message: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='错误信息')
