from backend.common.enums import StrEnum


class ConfigType(StrEnum):
    """配置类型"""

    email = 'EMAIL'
    user_security = 'USER_SECURITY'
    login = 'LOGIN'
    task = 'Task'
    storage = 'STORAGE'
    shop = 'SHOP'
    crawler = 'CRAWLER'
    invite = 'INVITE'

