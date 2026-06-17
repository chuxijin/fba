#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import hashlib
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from backend.common.log import log


class PKCS7Encoder:
    """PKCS7 编码器"""

    @staticmethod
    def decode(text: bytes) -> bytes:
        """
        去除 PKCS7 填充

        :param text: 填充字节流
        :return:
        """
        pad = text[-1]
        if pad < 1 or pad > 32:
            pad = 0
        return text[:-pad]


class WecomMsgCrypt:
    """企业微信消息加解密工具类"""

    def __init__(self, token: str, encoding_aes_key: str, receive_id: str) -> None:
        """
        初始化加解密类

        :param token: 企业微信配置的 Token
        :param encoding_aes_key: 企业微信配置的 EncodingAESKey
        :param receive_id: 企业微信的 CorpID
        """
        self.token = token
        self.aes_key = base64.b64decode(encoding_aes_key + '=')
        self.receive_id = receive_id

    def verify_signature(self, msg_signature: str, timestamp: str, nonce: str, encrypt: str) -> bool:
        """
        校验签名

        :param msg_signature: 签名串
        :param timestamp: 时间戳
        :param nonce: 随机串
        :param encrypt: 加密消息体
        :return:
        """
        sort_list = sorted([self.token, timestamp, nonce, encrypt])
        sha1 = hashlib.sha1()
        sha1.update(''.join(sort_list).encode('utf-8'))
        calculated = sha1.hexdigest()
        return calculated == msg_signature

    def decrypt(self, encrypt: str) -> str:
        """
        解密企业微信消息并还原明文

        :param encrypt: 加密的 Base64 字符串
        :return:
        """
        try:
            cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(self.aes_key[:16]), backend=default_backend())
            decryptor = cipher.decryptor()
            raw_bytes = decryptor.update(base64.b64decode(encrypt)) + decryptor.finalize()

            plain_bytes = PKCS7Encoder.decode(raw_bytes)

            content_len = struct.unpack('>I', plain_bytes[16:20])[0]
            xml_content = plain_bytes[20 : 20 + content_len].decode('utf-8')
            from_corpid = plain_bytes[20 + content_len :].decode('utf-8')

            if from_corpid != self.receive_id:
                log.error(f'微信解密时 CorpID 校验不匹配: 期望 {self.receive_id}, 实际 {from_corpid}')
                raise ValueError('CorpID mismatch')

            return xml_content
        except Exception as e:
            log.error(f'企业微信消息解密失败: {e}')
            raise ValueError(f'Decrypt failed: {e}') from e
