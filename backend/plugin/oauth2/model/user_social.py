import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class UserSocial(Base):
    """用户社交表（OAuth2）"""

    __tablename__ = 'sys_user_social'
    __table_args__ = (
        sa.UniqueConstraint('source', 'openid', name='uq_oauth2_source_openid'),
        sa.Index('ix_oauth2_unionid', 'unionid'),
        {'comment': '用户社交表（OAuth2）'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    source: Mapped[str] = mapped_column(sa.String(32), comment='第三方用户来源')
    # 逻辑外键
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户关联ID')
    sid: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='第三方用户 ID (普通OAuth2标识)')
    openid: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='平台 OpenID (适用于微信/QQ)')
    unionid: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='跨端 UnionID (微信全生态互通标识)')
    extra: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='平台扩展数据(存session_key等)')
