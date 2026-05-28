from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class OCResource(Base):
    """笔试面试资料包模型"""

    __tablename__ = 'oc_resource'

    id: Mapped[id_key] = mapped_column(init=False)
    title: Mapped[str] = mapped_column(String(255), comment='资料包标题')
    image: Mapped[str | None] = mapped_column(String(500), default=None, comment='图片地址')
    baidu_link: Mapped[str | None] = mapped_column(String(500), default=None, comment='百度云链接')
    extract_code: Mapped[str | None] = mapped_column(String(10), default=None, comment='提取码')
