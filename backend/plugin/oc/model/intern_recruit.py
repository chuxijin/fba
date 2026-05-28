from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class InternRecruit(Base):
    """实习岗位表"""

    __tablename__ = 'oc_intern_recruit'

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, comment='岗位ID（使用源网站ID）')
    company_name: Mapped[str] = mapped_column(sa.Text, index=True, comment='公司名称')
    company_type: Mapped[str] = mapped_column(sa.String(64), comment='公司类型')
    industry: Mapped[str] = mapped_column(sa.String(128), comment='所属行业')
    recruitment_type: Mapped[str] = mapped_column(sa.String(64), comment='招聘类型')
    recruit_target: Mapped[str] = mapped_column(sa.String(128), comment='招聘对象')
    location: Mapped[str] = mapped_column(sa.Text, comment='工作地点')
    positions: Mapped[str] = mapped_column(sa.Text, comment='岗位名称')
    update_time: Mapped[date] = mapped_column(sa.Date, comment='更新时间')
    application_status: Mapped[str] = mapped_column(
        sa.String(32),
        default='未投递',
        comment='投递进度'
    )
    deadline: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='截止时间')
    apply_link: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='投递链接')
    notice_link: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='招聘公告链接')
    referral_code: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='内推码')
    remark: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='备注')
