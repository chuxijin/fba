from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.enums import ApplicationStatus
from backend.common.model import Base, UserMixin, snowflake_id_key


class JobApplication(Base, UserMixin):
    """
    用户岗位投递进度表
    """
    __tablename__ = "job_application"

    id: Mapped[snowflake_id_key] = mapped_column(init=False)
    job_posting_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("job_posting.id"), comment="招聘信息 ID")
    application_status: Mapped[ApplicationStatus] = mapped_column(String(255), comment="投递状态")
