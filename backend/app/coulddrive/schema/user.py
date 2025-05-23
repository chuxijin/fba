from typing import Optional
from pydantic import BaseModel, Field

from app.coulddrive.service.utils import human_size


class BaseUserInfo(BaseModel):
    """
    网盘用户信息基类
    
    提供网盘用户信息的基础属性和方法
    """
    user_id: str = Field("", description="用户ID")
    username: str = Field("", description="用户名")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    quota: Optional[int] = Field(None, description="总空间配额（字节）")
    used: Optional[int] = Field(None, description="已使用空间（字节）")
    is_vip: Optional[bool] = Field(None, description="是否是VIP用户")
    is_supervip: Optional[bool] = Field(None, description="是否是超级会员")
    # Pydantic V2 建议使用 model_config 来定义额外字段的处理方式
    # 如果希望允许未定义的字段，可以使用 extra = 'allow'
    # model_config = {
    #     "extra": "allow" 
    # }
    # 或者，如果希望严格匹配字段，则不需要设置 extra 或设为 'forbid'

    @property
    def formatted_quota(self) -> str:
        """格式化的总空间配额"""
        return human_size(self.quota) if self.quota is not None else "未知"
    
    @property
    def formatted_used(self) -> str:
        """格式化的已使用空间"""
        return human_size(self.used) if self.used is not None else "未知"
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"BaseUserInfo(user_id='{self.user_id}', username='{self.username}')"
    
class UserFriend(BaseModel):
    """
    百度网盘好友信息
    
    uk: 用户ID
    uname: 用户名
    nick_name: 昵称
    avatar_url: 头像URL
    is_friend: 好友关系(0:非好友, 1:单向关注, 2:互相关注)
    """
    uk: int
    uname: str
    nick_name: str
    avatar_url: str
    is_friend: int


class UserGroup(BaseModel):
    """
    百度网盘群组信息
    
    gid: 群组ID
    gnum: 群号
    name: 群名称
    type: 群类型
    status: 群状态(1:正常)
    """
    gid: str
    gnum: str
    name: str
    type: str
    status: str