from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UniversalText, UserMixin, id_key


class Content(Base, UserMixin):
    """通用内容表"""

    __tablename__ = 'sys_content'
    __table_args__ = (
        sa.Index('ix_sys_content_app_code', 'app_code'),
        sa.Index('ix_sys_content_tags', 'tags', postgresql_using='gin'),
        sa.Index('ix_sys_content_extra', 'extra', postgresql_using='gin'),
        {'comment': '系统通用内容表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    # 归属应用
    app_code: Mapped[str] = mapped_column(sa.String(32), comment='应用标识（如 blog, notice, gongkao）')

    # 基础信息
    title: Mapped[str] = mapped_column(sa.String(255), comment='标题')
    slug: Mapped[str | None] = mapped_column(sa.String(255), unique=True, default=None, comment='别名（固定链接标识）')

    # 内容字段
    content_json: Mapped[dict | None] = mapped_column(JSONB, default=None, comment='Tiptap JSON 内容')
    content_html: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='预渲染 HTML')
    summary: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='摘要')
    cover_image: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='封面图 URL')

    # 分类与标签
    category_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='关联分类 ID')
    tags: Mapped[list | None] = mapped_column(JSONB, default=None, comment='标签')

    # 状态与控制
    is_pinned: Mapped[bool] = mapped_column(default=False, comment='是否置顶')
    is_public: Mapped[bool] = mapped_column(default=True, comment='是否公开')
    is_published: Mapped[bool] = mapped_column(default=False, comment='是否发布')
    publish_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='发表时间')

    # 统计与排序
    view_count: Mapped[int] = mapped_column(default=0, comment='浏览量')
    sort_order: Mapped[int] = mapped_column(default=0, comment='排序权重')

    # 扩展
    extra: Mapped[dict | None] = mapped_column(JSONB, default=None, comment='元数据')
