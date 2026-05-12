#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UniversalText, id_key

CompatibleJSON = sa.JSON().with_variant(JSONB, 'postgresql')


class RenderBookJob(Base):
    """题本渲染任务表"""

    __tablename__ = 'render_book_job'
    __table_args__ = (
        sa.Index('idx_render_book_job_status_created', 'status', 'created_time'),
        sa.Index('idx_render_book_job_user_created', 'user_id', 'created_time'),
        sa.Index('idx_render_book_job_template', 'template_key'),
        sa.UniqueConstraint('job_id', name='uq_render_book_job_job_id'),
        sa.CheckConstraint("mode IN ('preview','final')", name='ck_render_book_job_mode'),
        sa.CheckConstraint(
            "status IN ('accepted','running','succeeded','failed')",
            name='ck_render_book_job_status',
        ),
        sa.CheckConstraint(
            "(book_kind IS NULL OR book_kind IN ('module','wrong','exam','custom'))",
            name='ck_render_book_job_book_kind',
        ),
        sa.CheckConstraint(
            "(solution_mode IS NULL OR solution_mode IN ('none','separate','inline','appendix'))",
            name='ck_render_book_job_solution_mode',
        ),
        {'comment': '题本渲染任务表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    job_id: Mapped[str] = mapped_column(sa.String(64), index=True, comment='外部任务 ID')
    template_key: Mapped[str] = mapped_column(sa.String(100), comment='模板键')
    title: Mapped[str] = mapped_column(sa.String(200), comment='题本标题')
    user_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='业务用户 ID')
    mode: Mapped[str] = mapped_column(sa.String(16), default='final', comment='任务模式')
    status: Mapped[str] = mapped_column(sa.String(16), default='accepted', comment='任务状态')
    subtitle: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='题本副标题')
    subject: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='学科')
    book_kind: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='题本类型')
    solution_mode: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='解析排版方式')
    filters: Mapped[dict | None] = mapped_column(CompatibleJSON, default=None, comment='筛选条件')
    options: Mapped[dict | None] = mapped_column(CompatibleJSON, default=None, comment='渲染选项')
    output_targets: Mapped[dict | None] = mapped_column(CompatibleJSON, default=None, comment='输出目标')
    render_variants: Mapped[list[str] | None] = mapped_column(CompatibleJSON, default=None, comment='渲染变体')
    metadata_json: Mapped[dict | None] = mapped_column('metadata', CompatibleJSON, default=None, comment='附加元数据')
    payload_path: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='payload.json 路径')
    question_count: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='题目数量')
    material_count: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='材料数量')
    output_path: Mapped[str | None] = mapped_column(sa.String(1000), default=None, comment='主输出路径或地址')
    error_message: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='错误信息')
    del_flag: Mapped[bool] = mapped_column(default=False, comment='删除标志（False 存在 True 删除）')

    files: Mapped[list['RenderBookJobFile']] = relationship(
        init=False,
        back_populates='job',
        lazy='noload',
        cascade='all, delete-orphan',
    )


class RenderBookJobFile(Base):
    """题本渲染文件表"""

    __tablename__ = 'render_book_job_file'
    __table_args__ = (
        sa.Index('idx_render_book_job_file_job_kind', 'render_job_id', 'file_kind'),
        sa.CheckConstraint(
            "file_kind IN ('question_pdf','solution_pdf','combined_pdf')",
            name='ck_render_book_job_file_kind',
        ),
        sa.CheckConstraint(
            "(render_variant IS NULL OR render_variant IN "
            "('questions_only','solutions_only','combined_inline','combined_appendix'))",
            name='ck_render_book_job_file_variant',
        ),
        sa.CheckConstraint(
            "storage_type IN ('local','oss')",
            name='ck_render_book_job_file_storage',
        ),
        sa.CheckConstraint(
            "status IN ('available','failed')",
            name='ck_render_book_job_file_status',
        ),
        {'comment': '题本渲染文件表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    render_job_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('render_book_job.id', ondelete='CASCADE'),
        comment='渲染任务主键 ID',
    )
    file_kind: Mapped[str] = mapped_column(sa.String(32), comment='文件类型')
    filename: Mapped[str] = mapped_column(sa.String(255), comment='文件名')
    render_variant: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='渲染变体')
    storage_type: Mapped[str] = mapped_column(sa.String(16), default='local', comment='存储类型')
    status: Mapped[str] = mapped_column(sa.String(16), default='available', comment='文件状态')
    content_type: Mapped[str] = mapped_column(sa.String(100), default='application/pdf', comment='内容类型')
    size_bytes: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='文件大小（字节）')
    local_path: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='本地文件路径')
    object_key: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='OSS 对象 Key')
    url: Mapped[str | None] = mapped_column(sa.String(1000), default=None, comment='访问地址')
    error_message: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='错误信息')

    job: Mapped[RenderBookJob] = relationship(init=False, back_populates='files', lazy='noload')
