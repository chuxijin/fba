#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class BiliTaskConfig(Base):
    """B 站定时任务配置表"""

    __tablename__ = 'bili_task_config'

    id: Mapped[id_key] = mapped_column(init=False)

    # ===== 必填字段（无默认值） =====
    task_name: Mapped[str] = mapped_column(sa.String(128), unique=True, index=True, comment='任务名称')
    task_type: Mapped[str] = mapped_column(
        sa.String(32),
        index=True,
        comment='任务类型: reply_my_message/reply_my_comment/send_to_others_comment',
    )
    start_time: Mapped[str] = mapped_column(sa.String(8), comment='开始时间 HH:MM:SS')
    end_time: Mapped[str] = mapped_column(sa.String(8), comment='结束时间 HH:MM:SS')
    account_id: Mapped[int] = mapped_column(sa.BigInteger, comment='执行账号 ID')
    execution_status: Mapped[str] = mapped_column(sa.String(16), default='RUNNING', comment='执行状态: SUCCESS/FAIL/FATAL')

    # ===== 可选字段（有默认值） =====
    is_enabled: Mapped[bool] = mapped_column(sa.Boolean, default=True, comment='是否启用')
    rest_start_time: Mapped[str | None] = mapped_column(sa.String(8), default=None, comment='休息开始时间 HH:MM:SS')
    rest_end_time: Mapped[str | None] = mapped_column(sa.String(8), default=None, comment='休息结束时间 HH:MM:SS')
    check_interval_min: Mapped[int] = mapped_column(sa.Integer, default=30, comment='检查间隔最小值（秒）')
    check_interval_max: Mapped[int] = mapped_column(sa.Integer, default=60, comment='检查间隔最大值（秒）')
    work_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='关联作品 ID（仅评论相关任务）')
    template_ids: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='关联模板 ID 列表（JSON 数组）')
    filter_config: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='筛选条件配置（等级、注册时间等）')
    is_first_run: Mapped[bool] = mapped_column(sa.Boolean, default=True, comment='是否首次运行（首次全量扫描）')
    last_processed_id: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='最后处理的评论/私信 ID')
    last_processed_time: Mapped[str | None] = mapped_column(sa.DateTime, default=None, comment='最后处理的内容时间')
    last_run_time: Mapped[str | None] = mapped_column(sa.DateTime, default=None, comment='上次运行时间')
    last_check_time: Mapped[str | None] = mapped_column(sa.DateTime, default=None, comment='上次检查时间')
    next_run_time: Mapped[str | None] = mapped_column(sa.DateTime, default=None, comment='下次运行时间')
    run_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='运行次数')
    reply_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='回复成功次数')
    send_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='私信发送成功次数')
    fail_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='失败次数')
    last_error: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='最后错误信息')
    description: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='任务描述')
