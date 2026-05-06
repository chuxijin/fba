#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import hmac


def verify_agiso_signature(json_str: str, timestamp: str, sign: str, app_secret: str) -> bool:
    """
    验证阿奇索推送签名

    :param json_str: JSON 字符串
    :param timestamp: 时间戳
    :param sign: 签名
    :param app_secret: AppSecret
    :return:
    """
    sign_str = f'{app_secret}json{json_str}timestamp{timestamp}{app_secret}'
    calculated_sign = hashlib.md5(sign_str.encode('utf-8'), usedforsecurity=False).hexdigest()
    return hmac.compare_digest(calculated_sign.lower(), sign.lower())


def generate_agiso_signature(json_str: str, timestamp: str, app_secret: str) -> str:
    """
    生成阿奇索签名

    :param json_str: JSON 字符串
    :param timestamp: 时间戳
    :param app_secret: AppSecret
    :return:
    """
    sign_str = f'{app_secret}json{json_str}timestamp{timestamp}{app_secret}'
    return hashlib.md5(sign_str.encode('utf-8'), usedforsecurity=False).hexdigest()
