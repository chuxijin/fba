"""默认昵称生成工具。

昵称与用户名是两种东西：用户名承担唯一标识（如 ``wx_`` + openid 后缀），昵称只负责展示。
微信授权登录拿不到真实昵称时，如果统一写死「微信用户」，账号一多就无法区分，
所以这里生成带随机后缀的默认昵称，用户后续可在个人资料里自行修改。
"""

import string

from secrets import choice

DEFAULT_NICKNAME_PREFIX = '微信用户'
DEFAULT_NICKNAME_SUFFIX_LENGTH = 6
NICKNAME_ALPHABET = string.ascii_lowercase + string.digits


def generate_default_nickname(
    prefix: str = DEFAULT_NICKNAME_PREFIX,
    suffix_length: int = DEFAULT_NICKNAME_SUFFIX_LENGTH,
) -> str:
    """
    生成带随机后缀的默认昵称

    :param prefix: 昵称前缀
    :param suffix_length: 随机后缀长度
    :return: 形如 ``微信用户_9f3ka2`` 的昵称
    """
    if suffix_length <= 0:
        return prefix

    suffix = ''.join(choice(NICKNAME_ALPHABET) for _ in range(suffix_length))
    return f'{prefix}_{suffix}'
