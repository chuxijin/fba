"""内推码模型"""

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import DataClassBase, DateTimeMixin, UserMixin, id_key


class ReferralCode(DataClassBase, DateTimeMixin, UserMixin):
    """内推码表"""

    __tablename__ = 'oc_referral_code'

    id: Mapped[id_key] = mapped_column(init=False)
    company_name: Mapped[str] = mapped_column(sa.String(128), index=True, comment='企业名称')
    referral_code: Mapped[str] = mapped_column(sa.String(128), comment='内推码')
    remark: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='备注')
