#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Literal

from pydantic import Field, field_validator

from backend.common.schema import SchemaBase


class CodeGeneratorConfig(SchemaBase):
    """激活码生成器配置"""

    groups: int = Field(default=3, ge=1, le=10, description='分组数量')
    group_length: int = Field(default=5, ge=3, le=10, description='每组长度')
    separator: str = Field(default='-', max_length=3, description='分隔符')
    prefix: str = Field(default='', max_length=20, description='前缀')
    suffix: str = Field(default='', max_length=20, description='后缀')
    use_digits: bool = Field(default=True, description='是否包含数字')
    use_letters: bool = Field(default=True, description='是否包含字母')
    letter_case: Literal['upper', 'lower', 'mixed'] = Field(default='upper', description='字母大小写')
    use_special: bool = Field(default=False, description='是否包含特殊符号')
    special_chars: str = Field(default='', max_length=20, description='特殊符号集合')
    exclude_chars: list[str] = Field(default_factory=lambda: ['O', '0', 'I', '1'], description='排除字符')
    exclude_words: list[str] = Field(default_factory=list, description='排除敏感词')
    use_checksum: bool = Field(default=False, description='是否使用校验位')

    @field_validator('letter_case')
    def validate_letter_case(cls, v: str) -> str:
        """验证字母大小写配置"""
        if v not in ['upper', 'lower', 'mixed']:
            raise ValueError('letter_case 必须是 upper、lower 或 mixed')
        return v

    @field_validator('groups', 'group_length')
    def validate_positive(cls, v: int) -> int:
        """验证正数"""
        if v < 1:
            raise ValueError('必须大于 0')
        return v


class DefaultCodeConfig(SchemaBase):
    """默认配置集合"""

    @staticmethod
    def vip_card() -> CodeGeneratorConfig:
        """VIP 会员卡配置"""
        return CodeGeneratorConfig(
            groups=3,
            group_length=5,
            separator='-',
            prefix='VIP',
            use_digits=True,
            use_letters=True,
            letter_case='upper',
            exclude_chars=['O', '0', 'I', '1'],
        )

    @staticmethod
    def game_item() -> CodeGeneratorConfig:
        """游戏道具配置"""
        return CodeGeneratorConfig(
            groups=4,
            group_length=4,
            separator='-',
            prefix='GAME',
            use_digits=True,
            use_letters=False,
            letter_case='upper',
        )

    @staticmethod
    def coupon() -> CodeGeneratorConfig:
        """优惠券配置"""
        return CodeGeneratorConfig(
            groups=2,
            group_length=6,
            separator='-',
            prefix='DC',
            use_digits=True,
            use_letters=True,
            letter_case='mixed',
            exclude_chars=['O', '0', 'I', '1', 'l'],
        )

    @staticmethod
    def short_code() -> CodeGeneratorConfig:
        """短码配置"""
        return CodeGeneratorConfig(
            groups=1,
            group_length=8,
            separator='',
            use_digits=True,
            use_letters=True,
            letter_case='upper',
            exclude_chars=['O', '0', 'I', '1'],
        )

    @staticmethod
    def high_security() -> CodeGeneratorConfig:
        """高安全配置"""
        return CodeGeneratorConfig(
            groups=5,
            group_length=5,
            separator='-',
            use_digits=True,
            use_letters=True,
            letter_case='upper',
            exclude_chars=['O', '0', 'I', '1'],
            use_checksum=True,
        )
