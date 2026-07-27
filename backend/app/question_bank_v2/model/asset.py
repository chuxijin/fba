from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UserMixin, id_key

from .common import CompatibleJSONB

if TYPE_CHECKING:
    from .material import QbMaterialRevision
    from .practice import QbQuestionAttempt
    from .question import QbQuestionRevision


class QbAsset(Base, UserMixin):
    """Stable binary asset metadata, independent from any storage provider."""

    __tablename__ = 'qbank_v2_asset'
    __table_args__ = (
        sa.UniqueConstraint('asset_key', 'deleted', name='uq_qbv2_asset_key_deleted'),
        sa.CheckConstraint('size_bytes >= 0', name='ck_qbv2_asset_size'),
        sa.CheckConstraint('width IS NULL OR width > 0', name='ck_qbv2_asset_width'),
        sa.CheckConstraint('height IS NULL OR height > 0', name='ck_qbv2_asset_height'),
        sa.CheckConstraint('duration_ms IS NULL OR duration_ms >= 0', name='ck_qbv2_asset_duration'),
        sa.CheckConstraint(
            "visibility IN ('private','internal','public')",
            name='ck_qbv2_asset_visibility',
        ),
        sa.CheckConstraint(
            "status IN ('pending','ready','quarantined','archived')",
            name='ck_qbv2_asset_status',
        ),
        sa.CheckConstraint(
            "visibility <> 'private' OR owner_id IS NOT NULL",
            name='ck_qbv2_asset_private_owner',
        ),
        sa.Index('ix_qbv2_asset_hash_size', 'content_hash', 'size_bytes'),
        sa.Index('ix_qbv2_asset_owner_status', 'owner_id', 'status', 'created_time'),
        {'comment': '题库二进制资产元数据表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    asset_key: Mapped[str] = mapped_column(sa.String(64), comment='稳定资产业务键')
    content_hash: Mapped[str] = mapped_column(sa.String(64), comment='原始字节 SHA-256')
    mime_type: Mapped[str] = mapped_column(sa.String(128), comment='MIME 类型')
    size_bytes: Mapped[int] = mapped_column(sa.BigInteger, comment='原始字节数')
    owner_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='RESTRICT'),
        default=None,
        comment='私有资产所有者',
    )
    original_name: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='原始文件名')
    width: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='图片或视频原始宽度')
    height: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='图片或视频原始高度')
    duration_ms: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='音视频时长毫秒')
    visibility: Mapped[str] = mapped_column(sa.String(16), default='internal', comment='可见范围')
    status: Mapped[str] = mapped_column(sa.String(16), default='pending', comment='资产处理状态')
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        'metadata',
        CompatibleJSONB,
        default_factory=dict,
        comment='编码、版权和处理扩展元数据',
    )

    locations: Mapped[list[QbAssetLocation]] = relationship(
        init=False,
        back_populates='asset',
        cascade='all, delete-orphan',
        lazy='noload',
    )


class QbAssetLocation(Base, UserMixin):
    """One physical copy of an asset; supports storage migration and replicas."""

    __tablename__ = 'qbank_v2_asset_location'
    __table_args__ = (
        sa.UniqueConstraint(
            'provider',
            'namespace',
            'object_key',
            'deleted',
            name='uq_qbv2_asset_location_object',
        ),
        sa.CheckConstraint(
            "status IN ('pending','available','missing','retired')",
            name='ck_qbv2_asset_location_status',
        ),
        sa.Index('ix_qbv2_asset_location_asset', 'asset_id', 'status', 'is_primary'),
        sa.Index(
            'uq_qbv2_asset_location_primary',
            'asset_id',
            unique=True,
            postgresql_where=sa.text('is_primary AND deleted = 0'),
        ).ddl_if(dialect='postgresql'),
        {'comment': '题库资产物理存储位置表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    asset_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_asset.id', ondelete='CASCADE'),
        comment='资产 ID',
    )
    provider: Mapped[str] = mapped_column(sa.String(64), comment='存储服务商或驱动')
    object_key: Mapped[str] = mapped_column(sa.String(1024), comment='对象键或相对路径')
    namespace: Mapped[str] = mapped_column(sa.String(255), default='', comment='桶、容器或命名空间')
    etag: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='存储侧 ETag')
    is_primary: Mapped[bool] = mapped_column(default=False, comment='是否当前主位置')
    status: Mapped[str] = mapped_column(sa.String(16), default='pending', comment='副本状态')
    last_verified_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近校验时间')

    asset: Mapped[QbAsset] = relationship(init=False, back_populates='locations', lazy='noload')


class QbQuestionRevisionAsset(Base, UserMixin):
    """Named asset placement in an immutable question revision."""

    __tablename__ = 'qbank_v2_question_revision_asset'
    __table_args__ = (
        sa.UniqueConstraint(
            'question_revision_id',
            'link_key',
            'deleted',
            name='uq_qbv2_qrev_asset_key',
        ),
        sa.CheckConstraint('sort_order >= 0', name='ck_qbv2_qrev_asset_sort'),
        sa.CheckConstraint(
            "role IN ('stem','option','explanation','attachment','ocr_source','other')",
            name='ck_qbv2_qrev_asset_role',
        ),
        sa.Index('ix_qbv2_qrev_asset_order', 'question_revision_id', 'role', 'sort_order'),
        sa.Index('ix_qbv2_qrev_asset_reverse', 'asset_id'),
        {'comment': '题目版本资产关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_revision_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question_revision.id', ondelete='RESTRICT'),
        comment='题目版本 ID',
    )
    asset_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_asset.id', ondelete='RESTRICT'),
        comment='资产 ID',
    )
    link_key: Mapped[str] = mapped_column(sa.String(64), comment='版本内稳定引用键')
    role: Mapped[str] = mapped_column(sa.String(16), default='other', comment='资产用途')
    locator: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='选项、解析段落或内容块定位',
    )
    alt_text: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='无障碍替代文本')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='同用途展示顺序')

    question_revision: Mapped[QbQuestionRevision] = relationship(
        init=False,
        back_populates='assets',
        lazy='noload',
    )
    asset: Mapped[QbAsset] = relationship(init=False, lazy='noload')


class QbMaterialRevisionAsset(Base, UserMixin):
    """Named asset placement in an immutable material revision."""

    __tablename__ = 'qbank_v2_material_revision_asset'
    __table_args__ = (
        sa.UniqueConstraint(
            'material_revision_id',
            'link_key',
            'deleted',
            name='uq_qbv2_mrev_asset_key',
        ),
        sa.CheckConstraint('sort_order >= 0', name='ck_qbv2_mrev_asset_sort'),
        sa.CheckConstraint(
            "role IN ('content','page','image','audio','video','attachment','ocr_source','other')",
            name='ck_qbv2_mrev_asset_role',
        ),
        sa.Index('ix_qbv2_mrev_asset_order', 'material_revision_id', 'role', 'sort_order'),
        sa.Index('ix_qbv2_mrev_asset_reverse', 'asset_id'),
        {'comment': '材料版本资产关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    material_revision_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_material_revision.id', ondelete='RESTRICT'),
        comment='材料版本 ID',
    )
    asset_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_asset.id', ondelete='RESTRICT'),
        comment='资产 ID',
    )
    link_key: Mapped[str] = mapped_column(sa.String(64), comment='版本内稳定引用键')
    role: Mapped[str] = mapped_column(sa.String(16), default='content', comment='资产用途')
    locator: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='页码、内容块或展示定位',
    )
    alt_text: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='无障碍替代文本')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='同用途展示顺序')

    material_revision: Mapped[QbMaterialRevision] = relationship(
        init=False,
        back_populates='assets',
        lazy='noload',
    )
    asset: Mapped[QbAsset] = relationship(init=False, lazy='noload')


class QbQuestionAttemptAsset(Base, UserMixin):
    """Submitted image or attachment retained with an immutable attempt fact."""

    __tablename__ = 'qbank_v2_question_attempt_asset'
    __table_args__ = (
        sa.UniqueConstraint('attempt_id', 'link_key', 'deleted', name='uq_qbv2_attempt_asset_key'),
        sa.CheckConstraint(
            "role IN ('answer_image','attachment','ocr_source','other')",
            name='ck_qbv2_attempt_asset_role',
        ),
        sa.CheckConstraint('sort_order >= 0', name='ck_qbv2_attempt_asset_sort'),
        sa.Index('ix_qbv2_attempt_asset_order', 'attempt_id', 'role', 'sort_order'),
        sa.Index('ix_qbv2_attempt_asset_reverse', 'asset_id'),
        {'comment': '作答事实附件关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    attempt_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question_attempt.id', ondelete='CASCADE'),
        comment='作答事实 ID',
    )
    asset_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_asset.id', ondelete='RESTRICT'),
        comment='私有作答资产 ID',
    )
    link_key: Mapped[str] = mapped_column(sa.String(64), comment='本次作答内稳定引用键')
    role: Mapped[str] = mapped_column(sa.String(16), default='attachment', comment='附件用途')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='附件顺序')

    attempt: Mapped[QbQuestionAttempt] = relationship(
        init=False,
        back_populates='assets',
        lazy='noload',
    )
    asset: Mapped[QbAsset] = relationship(init=False, lazy='noload')
