#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
import string

# Base62 字符集: 0-9, a-z, A-Z
BASE62_CHARS = string.digits + string.ascii_lowercase + string.ascii_uppercase


def encode_base62(num: int) -> str:
    """
    将数字转换为 Base62 编码

    :param num: 正整数
    :return:
    """
    if num == 0:
        return BASE62_CHARS[0]

    result = []
    base = len(BASE62_CHARS)
    while num:
        result.append(BASE62_CHARS[num % base])
        num //= base
    return ''.join(reversed(result))


def decode_base62(code: str) -> int:
    """
    将 Base62 编码转换为数字

    :param code: Base62 编码字符串
    :return:
    """
    result = 0
    base = len(BASE62_CHARS)
    for char in code:
        result = result * base + BASE62_CHARS.index(char)
    return result


def generate_random_code(length: int = 6) -> str:
    """
    生成随机短码

    :param length: 短码长度
    :return:
    """
    return ''.join(random.choices(BASE62_CHARS, k=length))


def parse_device(user_agent: str | None) -> str | None:
    """
    从 User-Agent 解析设备类型

    :param user_agent: 浏览器UA字符串
    :return:
    """
    if not user_agent:
        return None

    ua = user_agent.lower()

    # 移动端优先检测
    if 'ipad' in ua:
        return 'iPad'
    if 'iphone' in ua:
        return 'iOS'
    if 'android' in ua:
        return 'Android'

    # 桌面端检测
    if 'windows' in ua:
        return 'Windows'
    if 'macintosh' in ua or 'mac os' in ua:
        return 'Mac'
    if 'linux' in ua:
        return 'Linux'

    return None


def parse_reference(user_agent: str | None, referer: str | None) -> str | None:
    """
    解析访问来源

    :param user_agent: 浏览器UA字符串
    :param referer: Referer 头
    :return:
    """
    if not user_agent:
        return None

    ua = user_agent.lower()

    # 微信浏览器
    if 'micromessenger' in ua:
        return '微信'

    # 支付宝
    if 'alipayclient' in ua:
        return '支付宝'

    # QQ 浏览器
    if 'qq/' in ua or 'qqbrowser' in ua:
        return 'QQ'

    # 微博
    if 'weibo' in ua:
        return '微博'

    # 抖音/头条
    if 'bytedancewebview' in ua or 'aweme' in ua:
        return '抖音'

    # 判断移动端浏览器 vs PC 浏览器
    mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'ipod']
    is_mobile = any(kw in ua for kw in mobile_keywords)

    if is_mobile:
        return '手机浏览器'
    return 'PC浏览器'
