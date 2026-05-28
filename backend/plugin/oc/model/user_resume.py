"""用户简历表"""

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import DataClassBase, DateTimeMixin, id_key


class UserResume(DataClassBase, DateTimeMixin):
    """用户简历表（存储加密数据）"""

    __tablename__ = 'oc_user_resume'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, unique=True, index=True, comment='用户ID')
    encrypted_data: Mapped[str] = mapped_column(sa.Text, comment='加密的简历数据')
    data_hash: Mapped[str] = mapped_column(sa.String(64), comment='数据哈希（用于校验）')
