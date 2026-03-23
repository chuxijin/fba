from backend.common.enums import StrEnum


class UserSocialType(StrEnum):
    """用户社交类型"""

    github = 'Github'
    google = 'Google'
    wechat_web = 'wechat_web'
    wechat_miniapp = 'wechat_miniapp'
    wechat_mp = 'wechat_mp'
    qq = 'QQ'


class UserSocialAuthType(StrEnum):
    """用户社交授权类型"""

    login = 'login'
    binding = 'binding'
