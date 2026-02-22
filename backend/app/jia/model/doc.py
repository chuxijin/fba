#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import BigInteger, ForeignKey, String, Text, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key


class JiaFolder(Base):
    """文档文件夹表（树形层级）"""

    __tablename__ = 'jia_folder'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, comment='用户 ID')
    name: Mapped[str] = mapped_column(String(128), comment='文件夹名称')
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('jia_folder.id', ondelete='CASCADE'), default=None, comment='父文件夹 ID'
    )
    icon: Mapped[str | None] = mapped_column(String(32), default=None, comment='图标 emoji')
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment='排序序号')

    # 关联
    children: Mapped[list['JiaFolder']] = relationship(
        init=False, back_populates='parent', cascade='all, delete-orphan', lazy='noload'
    )
    parent: Mapped['JiaFolder | None'] = relationship(
        init=False, back_populates='children', remote_side='JiaFolder.id', lazy='noload'
    )
    docs: Mapped[list['JiaDoc']] = relationship(
        init=False, back_populates='folder', cascade='all, delete-orphan', lazy='noload'
    )

    def __repr__(self) -> str:
        return f'<JiaFolder {self.name}>'


class JiaDoc(Base):
    """文档表 - 存储 AppFlowy Editor JSON 文档"""

    __tablename__ = 'jia_doc'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, comment='用户 ID')
    folder_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('jia_folder.id', ondelete='SET NULL'), default=None, index=True, comment='文件夹 ID'
    )

    # 标题与内容
    title: Mapped[str] = mapped_column(String(256), default='未命名文档', comment='文档标题')
    content: Mapped[dict | None] = mapped_column(JSONB, default=None, comment='AppFlowy Editor JSON（明文）')

    # 加密
    content_encrypted: Mapped[str | None] = mapped_column(Text, default=None, comment='AES-256-CBC 存储加密密文(hex)')
    access_encrypted: Mapped[bool] = mapped_column(default=False, comment='访问加密')
    access_password_hash: Mapped[str | None] = mapped_column(String(128), default=None, comment='访问密码 bcrypt 哈希')
    storage_encrypted: Mapped[bool] = mapped_column(default=False, comment='存储加密')

    # 状态
    is_pinned: Mapped[bool] = mapped_column(default=False, comment='是否置顶')
    is_trashed: Mapped[bool] = mapped_column(default=False, index=True, comment='是否在回收站')

    # 统计与元数据
    word_count: Mapped[int] = mapped_column(Integer, default=0, comment='字数统计')
    cover_url: Mapped[str | None] = mapped_column(String(512), default=None, comment='封面图 URL')
    tags: Mapped[list | None] = mapped_column(JSONB, default=None, comment='标签列表 ["日记","工作"]')
    meta: Mapped[dict | None] = mapped_column(JSONB, default=None, comment='扩展元数据（插件配置等）')

    # 关联
    folder: Mapped['JiaFolder | None'] = relationship(init=False, back_populates='docs', lazy='noload')
    assets: Mapped[list['JiaAsset']] = relationship(
        init=False, back_populates='doc', cascade='all, delete-orphan', lazy='noload'
    )

    def __repr__(self) -> str:
        return f'<JiaDoc {self.title}>'


class JiaAsset(Base):
    """文档资源表 - 图片、文件、音视频等"""

    __tablename__ = 'jia_asset'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, comment='用户 ID')

    # 文件信息（无默认值的字段在前）
    file_name: Mapped[str] = mapped_column(String(256), comment='原始文件名')
    storage_path: Mapped[str] = mapped_column(String(512), comment='服务器存储路径')
    mime_type: Mapped[str] = mapped_column(String(64), comment='MIME 类型')

    doc_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('jia_doc.id', ondelete='SET NULL'), default=None, index=True, comment='关联文档 ID'
    )
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, comment='文件大小（字节）')
    file_hash: Mapped[str | None] = mapped_column(String(64), default=None, comment='文件 SHA256（去重用）')

    # 扩展
    meta: Mapped[dict | None] = mapped_column(JSONB, default=None, comment='扩展信息（宽高、时长等）')

    # 关联
    doc: Mapped['JiaDoc | None'] = relationship(init=False, back_populates='assets', lazy='noload')

    def __repr__(self) -> str:
        return f'<JiaAsset {self.file_name}>'
