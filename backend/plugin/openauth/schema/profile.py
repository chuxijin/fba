from pydantic import Field

from backend.common.schema import SchemaBase


class GetOpenAuthProfile(SchemaBase):
    """最小公开账号资料，不返回手机号、邮箱、角色或内部权限。"""

    user_id: int = Field(description='当前授权用户 ID')
    nickname: str = Field(description='用户昵称')
    avatar: str | None = Field(default=None, description='用户头像地址')
    can_use_skill: bool = Field(default=False, description='是否具备 skill 业务使用资格（会员闸门）')
    skill_deny_message: str | None = Field(default=None, description='资格不足时的引导提示')
