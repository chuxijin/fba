#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
        :return:
        """
        try:
            session_key_bytes = base64.b64decode(self.session_key)
            encrypted_data_bytes = base64.b64decode(encrypted_data)
            iv_bytes = base64.b64decode(iv)

            cipher = Cipher(algorithms.AES(session_key_bytes), modes.CBC(iv_bytes), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted_data = decryptor.update(encrypted_data_bytes) + decryptor.finalize()

            padding_length = decrypted_data[-1]
            decrypted_data = decrypted_data[:-padding_length]

            result = json.loads(decrypted_data.decode('utf-8'))

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
        :return:
        """
        data = self.decrypt(encrypted_data, iv)
        phone_number = data.get('phoneNumber') or data.get('purePhoneNumber')
        if not phone_number:
            raise errors.AuthorizationError(msg='未找到手机号信息')
        return phone_number
