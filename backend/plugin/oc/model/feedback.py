from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import DataClassBase, DateTimeMixin, UserMixin, id_key


class OCFeedback(DataClassBase, DateTimeMixin, UserMixin):
    """用户反馈表"""

    __tablename__ = 'oc_feedback'

    id: Mapped[id_key] = mapped_column(init=False)
    type: Mapped[str] = mapped_column(String(20), comment='反馈类型: bug/feature/data/other')
    content: Mapped[str] = mapped_column(Text, comment='内容')
    ip: Mapped[str | None] = mapped_column(String(50), default=None, comment='IP地址')
    user_agent: Mapped[str | None] = mapped_column(String(500), default=None, comment='浏览器信息')
    status: Mapped[str] = mapped_column(String(20), default='pending', comment='状态: pending/processing/resolved/closed')
