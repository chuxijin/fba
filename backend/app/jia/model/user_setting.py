
from sqlalchemy import JSON, BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class JiaUserSetting(Base):
    """用户个性化设置表"""
    
    __tablename__ = 'jia_user_setting'

    id: Mapped[id_key] = mapped_column(init=False)
    
    # 关联用户 (一对一)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, comment='关联用户ID')
    
    # 界面设置
    theme: Mapped[str] = mapped_column(String(32), default='system', comment='主题模式(light/dark/system)')
    language: Mapped[str] = mapped_column(String(10), default='zh-CN', comment='语言偏好')
    
    # AI 偏好
    copilot_provider: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='默认Copilot供应商ID')
    copilot_model: Mapped[str | None] = mapped_column(String(64), default='gpt-4o', comment='默认Copilot模型')
    
    # 通知设置 (存复杂结构，方便扩展)
    # 示例: {"email_alert": true, "push_notify": false, "weekly_report": true}
    notifications: Mapped[dict | None] = mapped_column(JSON, default_factory=dict, comment='通知开关配置')
    
    # 扩展配置 (预留给未来的杂项设置)
    extra_config: Mapped[dict | None] = mapped_column(JSON, default_factory=dict, comment='其他扩展配置')
