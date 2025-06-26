#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
import string
from typing import Optional

from backend.plugin.app_auth.schema.redeem_code import CardKeyGenerationRequest, CharTypeOptions


class CardKeyService:
    """卡密生成服务类"""

    @staticmethod
    def _build_charset(options: CharTypeOptions) -> str:
        """根据选项构建字符集"""
        charset = ""
        if options.uppercase:
            charset += string.ascii_uppercase
        if options.lowercase:
            charset += string.ascii_lowercase
        if options.digits:
            charset += string.digits
        if options.special:
            # 默认使用常见的特殊字符，避免混淆字符如 ' " `
            charset += "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not charset:
            # 理论上 schema 验证会阻止这种情况，但作为保险
            raise ValueError("必须至少选择一种字符类型")
        return charset

    @staticmethod
    def _format_key(key: str, group_length: Optional[int], separator: Optional[str]) -> str:
        """格式化卡密，添加分隔符"""
        # 如果没有设置分组长度，直接返回原始密钥
        if group_length is None or group_length <= 0:
            return key

        # 如果分组长度大于等于密钥长度，也不分组
        if group_length >= len(key):
            return key

        if separator is None:
            separator = '-'

        # 计算分组
        grouped = []
        for i in range(0, len(key), group_length):
            grouped.append(key[i:i + group_length])
        
        return separator.join(grouped)

    @staticmethod
    def generate_card_keys(params: CardKeyGenerationRequest) -> list[str]:
        """
        生成指定数量和格式的卡密列表

        :param params: 卡密生成请求参数
        :return: 生成的卡密字符串列表
        """
        # 如果 char_types 为 None，使用默认值
        char_types = params.char_types or CharTypeOptions()
        charset = CardKeyService._build_charset(char_types)

        # 确定核心卡密长度
        core_length = params.key_length

        generated_keys = set()  # 使用 set 来确保唯一性，尽管碰撞概率极低
        attempts = 0
        max_attempts = params.count * 2  # 设置一个尝试上限，防止无限循环

        while len(generated_keys) < params.count and attempts < max_attempts:
            # 1. 生成核心随机部分
            core_key = ''.join(random.choice(charset) for _ in range(core_length))

            # 2. 格式化 (分组)
            formatted_core = CardKeyService._format_key(core_key, params.group_length, params.separator)

            # 3. 添加前后缀
            final_key = f"{params.prefix or ''}{formatted_core}{params.suffix or ''}"

            generated_keys.add(final_key)
            attempts += 1

        if len(generated_keys) < params.count:
            # 如果尝试了很多次仍然不够数量
            raise RuntimeError(f"无法生成足够数量的唯一卡密，请检查参数 (长度、字符集、数量)")

        return list(generated_keys)


card_key_service = CardKeyService()