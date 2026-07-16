#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key


class Category(Base, UserMixin):
    """系统分类表"""

    __tablename__ = 'sys_category'
    __table_args__ = (
        sa.Index('idx_category_app_type', 'app_code', 'type'),
        sa.Index('idx_category_parent', 'parent_id'),
        sa.UniqueConstraint('app_code', 'type', 'code', name='uq_category_app_type_code'),
        {'comment': '系统分类表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    # 必填字段（无默认值，必须在前）
    app_code: Mapped[str] = mapped_column(sa.String(32), comment='应用标识')
    name: Mapped[str] = mapped_column(sa.String(64), comment='分类名称')

    # 可选字段（有默认值）
    type: Mapped[str] = mapped_column(sa.String(32), default='default', comment='分类类型')
    code: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='分类编码')
    description: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='分类描述')

    # 树结构
    parent_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_category.id', ondelete='SET NULL'),
        default=None,
        index=True,
        comment='父级分类 ID',
    )
    level: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='层级')
    path: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='物化路径')

    # 父子关系
    parent: Mapped[Optional['Category']] = relationship(
        init=False, back_populates='children', remote_side='Category.id'
    )
    children: Mapped[list['Category']] = relationship(init=False, back_populates='parent')

    # 展示相关
    icon: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='图标')
    color: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='颜色')
    sort_order: Mapped[int] = mapped_column(default=0, comment='排序权重')

    # 状态控制
    status: Mapped[bool] = mapped_column(default=True, comment='状态')
    is_system: Mapped[bool] = mapped_column(default=False, comment='是否系统分类')

    # 扩展
    remark: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='备注')
    extra_data: Mapped[dict | None] = mapped_column(JSONB, default=None, comment='扩展数据')


class CategoryDocBinding(Base, UserMixin):
    """系统分类文档关联表"""

    __tablename__ = 'sys__doc_binding'
    __table_args__ = (
        sa.UniqueConstraint(
            'category_id',
            'relation_type',
            'halo_tree_name',
            'deleted',
            name='uq_sys_doc_binding_category_tree_deleted',
        ),
        sa.Index('idx_sys_doc_binding_category_enabled', 'category_id', 'enabled', 'sort_order'),
        sa.Index('idx_sys_doc_binding_halo_tree', 'halo_tree_name'),
        sa.Index('idx_sys_doc_binding_halo_doc', 'halo_doc_name'),
        {'comment': '系统分类文档关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    category_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_category.id', ondelete='CASCADE'),
        comment='系统分类 ID',
    )
    halo_project_name: Mapped[str] = mapped_column(sa.String(64), comment='Docsme 项目资源名称')
    halo_project_version_name: Mapped[str] = mapped_column(sa.String(64), comment='Docsme 项目版本资源名称')
    halo_tree_name: Mapped[str] = mapped_column(sa.String(64), comment='DocTree 节点资源名称')
    halo_doc_name: Mapped[str] = mapped_column(sa.String(64), comment='Doc 正文资源名称')
    title: Mapped[str] = mapped_column(sa.String(255), comment='文档标题')
    relation_type: Mapped[str] = mapped_column(sa.String(32), default='teaching', comment='关联类型')
    category_code: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='分类编码快照')
    category_path: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='分类路径快照')
    halo_doc_path: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='Docsme 文档路径')
    halo_permalink: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='Docsme 访问路径')
    enabled: Mapped[bool] = mapped_column(default=True, comment='是否启用')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')
    extra_data: Mapped[dict | None] = mapped_column(JSONB, default=None, comment='扩展数据')
