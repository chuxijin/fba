#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Optional

from pydantic import Field, model_validator

from backend.common.schema import SchemaBase


class CharTypeOptions(SchemaBase):
    """字符类型选项"""
    
    uppercase: bool = Field(True, description="包含大写字母 (A-Z)")
    lowercase: bool = Field(True, description="包含小写字母 (a-z)")
    digits: bool = Field(True, description="包含数字 (0-9)")
    special: bool = Field(False, description="包含特殊字符")

    @model_validator(mode='before')
    @classmethod
    def check_at_least_one_true(cls, data):
        """至少需要选择一种字符类型"""
        if isinstance(data, dict) and not any(data.values()):
            raise ValueError("至少需要选择一种字符类型")
        return data


class CardKeyGenerationRequest(SchemaBase):
    """卡密生成请求体"""
    
    char_types: CharTypeOptions = Field(default_factory=CharTypeOptions, description="字符类型选项")
    key_length: Optional[int] = Field(None, ge=4, le=128, description="核心卡密部分的总长度 (不分组时使用)")
    prefix: Optional[str] = Field(None, max_length=50, description="卡密前缀")
    suffix: Optional[str] = Field(None, max_length=50, description="卡密后缀")
    group_length: Optional[int] = Field(None, ge=2, le=32, description="每组字符的长度 (分组时使用)")
    group_count: Optional[int] = Field(None, ge=1, le=50, description="分组的数量 (分组时使用)")
    separator: str = Field("-", max_length=5, description="分组之间的分隔符")
    count: int = Field(..., ge=1, le=1000, description="要生成的卡密数量 (单次请求上限1000)")

    @model_validator(mode='before')
    @classmethod
    def check_length_definition(cls, values):
        """检查长度定义"""
        if not isinstance(values, dict):
            return values
            
        key_length = values.get('key_length')
        group_length = values.get('group_length')
        group_count = values.get('group_count')

        has_key_length = key_length is not None
        has_group_def = group_length is not None and group_count is not None

        if has_key_length and has_group_def:
            raise ValueError("不能同时指定 'key_length' 和 ('group_length', 'group_count')")
        if not has_key_length and not has_group_def:
            raise ValueError("必须指定 'key_length' 或同时指定 'group_length' 和 'group_count' 来定义卡密长度")
        if group_length is not None and group_count is None:
            raise ValueError("'group_length' 必须与 'group_count' 一同指定")
        if group_count is not None and group_length is None:
            raise ValueError("'group_count' 必须与 'group_length' 一同指定")

        # 如果使用分组定义，计算隐含的总长度并进行校验
        if has_group_def:
            calculated_length = group_length * group_count
            if not (4 <= calculated_length <= 128):
                raise ValueError(f"计算的总长度 ({calculated_length}) 必须在 4 到 128 之间")

        return values


class BatchCreateRedeemCodeWithGeneration(SchemaBase):
    """批量创建兑换码（带生成）参数"""
    
    application_id: int = Field(description='应用ID')
    batch_no: str = Field(description='批次号')
    duration_days: int = Field(description='有效期天数')
    max_devices: int = Field(1, description='最大设备数量')
    remark: str | None = Field(None, description='备注')
    generation_params: CardKeyGenerationRequest = Field(description='卡密生成参数')