#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class SysCat(Base, UserMixin):
    """系统分类表"""

    __tablename__ = 'sys_cat'
    __table_args__ = (
        sa.Index('idx_sys_cat_app_code', 'app_code'),
        sa.Index('idx_sys_cat_user_id', 'user_id'),
        sa.Index('idx_sys_cat_parent_id', 'parent_id'),
        sa.Index('idx_sys_cat_path', 'path'),
        sa.UniqueConstraint('app_code', 'name', 'parent_id', 'user_id', name='uq_sys_cat_app_name_parent_user'),
        {'comment': '系统分类表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    app_code: Mapped[str] = mapped_column(sa.String(32), comment='应用标识')
    name: Mapped[str] = mapped_column(sa.String(50), comment='分类名称')
    color: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='分类颜色')
    icon: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='分类图标')
    user_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='用户 ID（为空则为系统分类）')
    parent_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_cat.id', ondelete='SET NULL'),
        default=None,
        comment='父分类 ID',
    )
    level: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='层级')
    path: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='物化路径')
    sort_order: Mapped[int] = mapped_column(default=0, comment='排序权重')
    status: Mapped[bool] = mapped_column(default=True, comment='状态')
    remark: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='备注')


class SysCatTarget(Base, UserMixin):
    """系统分类关联表"""

    __tablename__ = 'sys_cat_target'
    __table_args__ = (
        sa.Index('idx_sys_cat_target_cat_id', 'cat_id'),
        sa.Index('idx_sys_cat_target_target', 'target_type', 'target_id'),
        sa.UniqueConstraint('cat_id', 'target_type', 'target_id', name='uq_sys_cat_target_unique'),
        {'comment': '系统分类关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    cat_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_cat.id', ondelete='CASCADE'),
        comment='分类 ID',
    )
    target_type: Mapped[str] = mapped_column(sa.String(50), comment='关联目标类型')
    target_id: Mapped[int] = mapped_column(sa.BigInteger, comment='关联目标 ID')
