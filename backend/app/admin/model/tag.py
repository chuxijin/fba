#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class SysTag(Base, UserMixin):
    """系统标签表"""

    __tablename__ = 'sys_tag'
    __table_args__ = (
        sa.Index('idx_sys_tag_app_code', 'app_code'),
        sa.Index('idx_sys_tag_user_id', 'user_id'),
        sa.UniqueConstraint('app_code', 'name', 'user_id', name='uq_sys_tag_app_name_user'),
        {'comment': '系统标签表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    app_code: Mapped[str] = mapped_column(sa.String(32), comment='应用标识')
    name: Mapped[str] = mapped_column(sa.String(50), comment='标签名称')
    color: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='标签颜色')
    icon: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='标签图标')
    user_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='用户 ID（为空则为系统级标签）')
    sort_order: Mapped[int] = mapped_column(default=0, comment='排序权重')
    status: Mapped[bool] = mapped_column(default=True, comment='状态')
    remark: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='备注')


class SysTagTarget(Base, UserMixin):
    """系统标签关联表"""

    __tablename__ = 'sys_tag_target'
    __table_args__ = (
        sa.Index('idx_sys_tag_target_tag_id', 'tag_id'),
        sa.Index('idx_sys_tag_target_target', 'target_type', 'target_id'),
        sa.UniqueConstraint('tag_id', 'target_type', 'target_id', name='uq_sys_tag_target_unique'),
        {'comment': '系统标签关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    tag_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_tag.id', ondelete='CASCADE'),
        comment='标签 ID',
    )
    target_type: Mapped[str] = mapped_column(sa.String(50), comment='关联目标类型')
    target_id: Mapped[int] = mapped_column(sa.BigInteger, comment='关联目标 ID')
