"""Formatter 配置表"""

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import DataClassBase, DateTimeMixin, id_key


class FormatterField(DataClassBase, DateTimeMixin):
    """字段配置表"""

    __tablename__ = 'oc_formatter_field'

    id: Mapped[id_key] = mapped_column(init=False)
    category: Mapped[str] = mapped_column(sa.String(50), index=True, comment='分类: basic_info, education_background 等')
    field_name: Mapped[str] = mapped_column(sa.String(50), comment='字段名: name, gender 等')
    chinese: Mapped[str] = mapped_column(sa.String(100), comment='中文名称')
    strategy: Mapped[str] = mapped_column(sa.String(30), default='input', comment='策略: input, drop_down_box, time 等')
    level: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='级别')
    field_order: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='排序')
    tips: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='提示')
    default_value: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='默认值')
    is_array: Mapped[bool] = mapped_column(sa.Boolean, default=False, comment='是否数组类型')
    is_hidden: Mapped[bool] = mapped_column(sa.Boolean, default=False, comment='是否隐藏')
    parent_field_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='父字段ID（用于复杂数组的子字段）')

    __table_args__ = (
        sa.UniqueConstraint('category', 'field_name', 'parent_field_id', name='uq_formatter_field'),
    )


class FormatterEmbedding(DataClassBase, DateTimeMixin):
    """标签匹配规则表"""

    __tablename__ = 'oc_formatter_embedding'

    id: Mapped[id_key] = mapped_column(init=False)
    field_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='关联字段ID')
    label: Mapped[str] = mapped_column(sa.String(200), comment='标签文本')
    value_script: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='值处理脚本')
    share_data_list: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='共享数据列表JSON')


class FormatterMapping(DataClassBase, DateTimeMixin):
    """下拉选项映射表"""

    __tablename__ = 'oc_formatter_mapping'

    id: Mapped[id_key] = mapped_column(init=False)
    field_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='关联字段ID')
    source_value: Mapped[str] = mapped_column(sa.String(100), comment='简历中的值')
    target_values: Mapped[str] = mapped_column(sa.String(500), comment='匹配目标值列表JSON')

    __table_args__ = (
        sa.UniqueConstraint('field_id', 'source_value', name='uq_formatter_mapping'),
    )
