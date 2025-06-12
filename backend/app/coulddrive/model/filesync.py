#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.common.model import Base, UserMixin, id_key

if TYPE_CHECKING:
    from backend.app.coulddrive.model.user import DriveAccount
    from backend.app.coulddrive.model.rule_template import RuleTemplate

class SyncConfig(Base, UserMixin):
    """文件同步配置表"""
    
    __tablename__ = "filesync_config"
    
    id: Mapped[id_key] = mapped_column(init=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="同步类型")
    src_path: Mapped[str] = mapped_column(String(1000), nullable=False, comment="源路径")
    dst_path: Mapped[str] = mapped_column(String(1000), nullable=False, comment="目标路径")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("yp_user.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联账号ID")
    
    # 有默认值的字段
    enable: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用", init=False)
    speed: Mapped[int] = mapped_column(Integer, default=0, comment="同步速度", init=False)
    method: Mapped[str] = mapped_column(String(20), default="copy", comment="同步方法", init=False)
    
    # 可选字段
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="备注", init=False)
    src_meta: Mapped[str | None] = mapped_column(Text, nullable=True, comment="源路径元数据", init=False)
    dst_meta: Mapped[str | None] = mapped_column(Text, nullable=True, comment="目标路径元数据", init=False)
    cron: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="定时任务表达式", init=False)
    end_time: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True, comment="结束时间", init=False)
    exclude_template_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("rule_template.id", ondelete="SET NULL"), nullable=True, comment="排除规则模板ID", init=False)
    rename_template_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("rule_template.id", ondelete="SET NULL"), nullable=True, comment="重命名规则模板ID", init=False)
    last_sync: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True, comment="最后同步时间", init=False)
    
    # 关系
    drive_account: Mapped["DriveAccount"] = relationship(
        "DriveAccount", 
        back_populates="sync_configs",
        init=False
    )
    sync_tasks: Mapped[list["SyncTask"]] = relationship(
        "SyncTask", 
        back_populates="sync_config", 
        cascade="all, delete-orphan",
        init=False
    )
    exclude_template: Mapped["RuleTemplate"] = relationship(
        "RuleTemplate",
        foreign_keys=[exclude_template_id],
        init=False
    )
    rename_template: Mapped["RuleTemplate"] = relationship(
        "RuleTemplate", 
        foreign_keys=[rename_template_id],
        init=False
    )
    
    def __repr__(self) -> str:
        return f"<SyncConfig(id={self.id}, type={self.type})>"

class SyncTask(Base, UserMixin):
    """文件同步任务表"""
    
    __tablename__ = "filesync_task"
    
    id: Mapped[id_key] = mapped_column(init=False)
    config_id: Mapped[int] = mapped_column(Integer, ForeignKey("filesync_config.id", ondelete="CASCADE"), nullable=False, index=True, comment="配置ID")
    
    # 有默认值的字段
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, comment="任务状态", init=False)
    dura_time: Mapped[int] = mapped_column(Integer, default=0, comment="持续时间", init=False)
    
    # 可选字段
    err_msg: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息", init=False)
    start_time: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True, comment="开始时间", init=False)
    task_num: Mapped[str | None] = mapped_column(Text, nullable=True, comment="任务统计信息", init=False)
    
    # 关系
    sync_config: Mapped["SyncConfig"] = relationship(
        "SyncConfig", 
        back_populates="sync_tasks",
        init=False
    )
    task_items: Mapped[list["SyncTaskItem"]] = relationship(
        "SyncTaskItem", 
        back_populates="sync_task", 
        cascade="all, delete-orphan",
        init=False
    )
    
    def __repr__(self) -> str:
        return f"<SyncTask(id={self.id}, status={self.status})>"

class SyncTaskItem(Base):
    """文件同步任务项表"""
    
    __tablename__ = "filesync_task_item"
    
    id: Mapped[id_key] = mapped_column(init=False)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("filesync_task.id", ondelete="CASCADE"), nullable=False, index=True, comment="任务ID")
    type: Mapped[str] = mapped_column(String(20), nullable=False, comment="操作类型")
    src_path: Mapped[str] = mapped_column(String(1000), nullable=False, comment="源文件路径")
    dst_path: Mapped[str] = mapped_column(String(1000), nullable=False, comment="目标文件路径")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="文件名")
    
    # 有默认值的字段
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, comment="文件大小", init=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, comment="状态", init=False)
    
    # 可选字段
    err_msg: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息", init=False)
    
    # 关系
    sync_task: Mapped["SyncTask"] = relationship(
        "SyncTask", 
        back_populates="task_items",
        init=False
    )
    
    def __repr__(self) -> str:
        return f"<SyncTaskItem(id={self.id}, file_name={self.file_name}, status={self.status})>"
    
