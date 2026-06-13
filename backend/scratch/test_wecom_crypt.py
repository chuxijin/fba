#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import os
import struct
import sys
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# 将项目根目录添加到 python path 中，以便正确导入
sys.path.insert(0, "d:\\100_Work\\101_Program\\Proj\\fba")

from backend.plugin.notify.utils.wecom_crypt import WecomMsgCrypt


class PKCS7Encoder:
    """ PKCS7 编码辅助器 """

    @staticmethod
    def encode(text_bytes: bytes) -> bytes:
        """
        填充字节流

        :param text_bytes: 未填充的原始字节
        :return:
        """
        text_length = len(text_bytes)
        amount_to_pad = 32 - (text_length % 32)
        if amount_to_pad == 0:
            amount_to_pad = 32
        pad = bytes([amount_to_pad] * amount_to_pad)
        return text_bytes + pad


def encrypt_msg(token: str, encoding_aes_key: str, corpid: str, xml_content: str) -> str:
    """
    模拟微信加密流程

    :param token: 微信Token
    :param encoding_aes_key: 微信AES密钥
    :param corpid: 企业微信 CorpID
    :param xml_content: 明文内容
    :return:
    """
    aes_key = base64.b64decode(encoding_aes_key + "=")
    random_bytes = os.urandom(16)
    xml_bytes = xml_content.encode("utf-8")
    corpid_bytes = corpid.encode("utf-8")

    # 组装明文格式：随机 16 字节 + 4 字节内容长度 + 明文 XML + CorpID
    raw_bytes = random_bytes + struct.pack(">I", len(xml_bytes)) + xml_bytes + corpid_bytes

    # 填充
    padded_bytes = PKCS7Encoder.encode(raw_bytes)

    # AES-256-CBC 加密
    cipher = Cipher(
        algorithms.AES(aes_key),
        modes.CBC(aes_key[:16]),
        backend=default_backend()
    )
    encryptor = cipher.encryptor()
    encrypted_bytes = encryptor.update(padded_bytes) + encryptor.finalize()
    return base64.b64encode(encrypted_bytes).decode("utf-8")


def test_crypt() -> None:
    """ 测试加解密流程 """
    token = "Fw3cS5kngD8zq8yuQBMvd7lctcI"
    encoding_aes_key = "AgIceoxoTrgM9E7Oqy5FpPIhlmkZIyG4YKgaTJ93Ihh"
    corpid = "ww76cf9d061d7ee3ec"

    # 我们测试用 XML
    test_xml = "<xml><ToUserName>TestUser</ToUserName><Content>Hello World</Content></xml>"

    print("【开始本地加解密集成测试】")
    # 1. 模拟微信服务器加密
    print("1. 模拟微信加密...")
    encrypted_data = encrypt_msg(token, encoding_aes_key, corpid, test_xml)
    print(f"密文数据: {encrypted_data}")

    # 2. 模拟本地解密
    print("2. 调用 WecomMsgCrypt 进行解密...")
    crypt = WecomMsgCrypt(token, encoding_aes_key, corpid)

    # 验证签名
    import hashlib
    sort_list = sorted([token, "123456789", "rnd_nonce", encrypted_data])
    sha1 = hashlib.sha1()
    sha1.update("".join(sort_list).encode("utf-8"))
    real_sig = sha1.hexdigest()

    sig_ok = crypt.verify_signature(real_sig, "123456789", "rnd_nonce", encrypted_data)
    print(f"真实签名校验结果: {'SUCCESS' if sig_ok else 'FAILED'}")
    assert sig_ok, "签名校验失败！"

    decrypted_xml = crypt.decrypt(encrypted_data)
    print(f"解密后明文: {decrypted_xml}")

    assert decrypted_xml == test_xml, "解密出来的明文与原 XML 不一致！"
    print("\n🎉【本地加解密集成测试全部成功！】")


if __name__ == "__main__":
    test_crypt()
