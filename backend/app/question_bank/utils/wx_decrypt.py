#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信加密数据解密工具

用于解密微信小程序通过 getPhoneNumber 等 API 返回的加密数据
"""
import base64
import json

from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from backend.common.exception import errors


class WXBizDataCrypt:
    """微信加密数据解密类"""

    def __init__(self, app_id: str, session_key: str):
        """
        初始化解密器

        :param app_id: 微信小程序 AppID
        :param session_key: 微信会话密钥
        """
        self.app_id = app_id
        self.session_key = session_key

    def decrypt(self, encrypted_data: str, iv: str) -> dict[str, Any]:
        """
        解密微信加密数据

        :param encrypted_data: 加密数据（Base64 编码）
        :param iv: 初始向量（Base64 编码）
        :return: 解密后的数据字典
        """
        try:
            # Base64 解码
            session_key_bytes = base64.b64decode(self.session_key)
            encrypted_data_bytes = base64.b64decode(encrypted_data)
            iv_bytes = base64.b64decode(iv)

            # AES 解密（AES-128-CBC 模式）
            cipher = Cipher(algorithms.AES(session_key_bytes), modes.CBC(iv_bytes), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted_data = decryptor.update(encrypted_data_bytes) + decryptor.finalize()

            # 移除 PKCS7 填充
            padding_length = decrypted_data[-1]
            decrypted_data = decrypted_data[:-padding_length]

            # 解析 JSON
            result = json.loads(decrypted_data.decode('utf-8'))

            # 验证 AppID
            if result.get('watermark', {}).get('appid') != self.app_id:
                raise errors.AuthorizationError(msg='AppID 校验失败')

            return result

        except (ValueError, KeyError) as e:
            raise errors.AuthorizationError(msg=f'数据解密失败: {str(e)}')

    def decrypt_phone_number(self, encrypted_data: str, iv: str) -> str:
        """
        解密手机号

        :param encrypted_data: 加密数据（Base64 编码）
        :param iv: 初始向量（Base64 编码）
        :return: 手机号（纯数字字符串）
        """
        data = self.decrypt(encrypted_data, iv)

        # 微信返回的手机号字段
        phone_number = data.get('phoneNumber') or data.get('purePhoneNumber')

        if not phone_number:
            raise errors.AuthorizationError(msg='未找到手机号信息')

        return phone_number
