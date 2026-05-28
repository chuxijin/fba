from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class UserApplication(Base):
    """用户投递记录表"""

    __tablename__ = 'oc_user_application'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        index=True,
        comment='用户ID'
    )
    job_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='岗位ID')
    job_type: Mapped[str] = mapped_column(sa.String(16), comment='岗位类型')
    application_status: Mapped[str] = mapped_column(
        sa.String(32),
        default='未投递',
        comment='投递状态'
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime,
        default=None,
        comment='投递时间'
    )
    remark: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='备注')
