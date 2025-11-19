#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class MembershipSchemaBase(SchemaBase):
    """会员权益基础"""

    user_id: int = Field(description='用户 ID')
    category: int = Field(description='会员分类（0=全部 1=题库 2=词库 3=资料包 4=商城）')
    res_type: str = Field(description='资源类型（category=整个分类 single=单个资源）')
    res_id: int | None = Field(None, description='资源 ID')
    res_name: str | None = Field(None, description='资源名称')
    pkg_id: int | None = Field(None, description='套餐 ID')
    pkg_name: str | None = Field(None, description='套餐名称')
    method: str = Field(description='开通方式（solo=购买 group=拼团 code=激活码 manual=手动 package=套餐）')
    act_code: str | None = Field(None, description='激活码')
    operator_id: int | None = Field(None, description='操作人 ID')
    order_id: int | None = Field(None, description='订单 ID')
    start_time: datetime = Field(description='生效时间')
    end_time: datetime = Field(description='到期时间')
    status: int = Field(default=1, description='状态（0 失效 1 有效）')
    auto_renew: bool = Field(default=False, description='自动续费')
    extra: dict | None = Field(None, description='扩展数据')


class GetMembershipDetail(MembershipSchemaBase):
    """会员权益详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='会员权益 ID')
    created_time: datetime = Field(description='创建时间')


class CreateMembershipParam(SchemaBase):
    """创建会员权益参数"""

    user_id: int = Field(description='用户 ID')
    category: int = Field(description='会员分类（0=全部 1=题库 2=词库 3=资料包 4=商城）')
    res_type: str = Field(description='资源类型（category=整个分类 single=单个资源）')
    res_id: int | None = Field(None, description='资源 ID')
    res_name: str | None = Field(None, description='资源名称')
    method: str = Field(default='manual', description='开通方式（solo=购买 group=拼团 code=激活码 manual=手动 package=套餐）')
    start_time: datetime = Field(description='生效时间')
    end_time: datetime = Field(description='到期时间')
    operator_id: int | None = Field(None, description='操作人 ID')


class UpdateMembershipParam(SchemaBase):
    """更新会员权益参数"""

    end_time: datetime | None = Field(None, description='到期时间')
    status: int | None = Field(None, description='状态（0 失效 1 有效）')
    auto_renew: bool | None = Field(None, description='自动续费')


class DeleteMembershipParam(SchemaBase):
    """删除会员权益参数"""

    ids: list[int] = Field(description='会员权益 ID 列表')


class MembershipParam(SchemaBase):
    """会员权益查询参数"""

    user_id: int | None = Field(None, description='用户 ID')
    category: int | None = Field(None, description='会员分类')
    status: int | None = Field(None, description='状态')
