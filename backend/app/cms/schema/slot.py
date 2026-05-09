#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ============ 运营位 ============
class CreateSlotParam(SchemaBase):
    """创建运营位参数"""

    code: str = Field(min_length=1, max_length=64, description='业务码')
    name: str = Field(min_length=1, max_length=128, description='内部名称')
    slot_type: str = Field(min_length=1, max_length=32, description='形态(curtain/banner/popup/splash/float/notice)')
    scene: str = Field(min_length=1, max_length=64, description='触发场景')
    title: str | None = Field(None, max_length=255, description='标题')
    subtitle: str | None = Field(None, max_length=255, description='副标题/摘要')
    image_url: str | None = Field(None, max_length=500, description='主图 URL')
    detail: str | None = Field(None, description='富文本详情')
    jump_type: str = Field(default='none', max_length=32, description='跳转类型(none/url/miniprogram/quest/content/custom)')
    jump_target: str | None = Field(None, max_length=500, description='跳转目标(URL 或业务 ID)')
    jump_extra: dict | None = Field(None, description='扩展跳转参数')
    start_time: datetime | None = Field(None, description='投放开始时间')
    end_time: datetime | None = Field(None, description='投放结束时间')
    status: int = Field(default=0, ge=0, le=2, description='状态(0 草稿 1 上线 2 已下线)')
    priority: int = Field(default=0, description='优先级(数字越大越靠前)')
    target_user_type: int = Field(default=0, ge=0, le=99, description='目标用户类型')
    target_min_member_level: int = Field(default=0, ge=0, description='最低会员等级权重(0 不限)')
    target_extra: dict | None = Field(None, description='扩展分群条件')
    max_show_per_user: int = Field(default=0, ge=0, description='单用户终生最多展示次数(0 不限)')
    max_show_per_day_per_user: int = Field(default=0, ge=0, description='单用户每日最多展示次数(0 不限)')
    close_dismiss_count: int = Field(default=0, ge=0, description='关闭 N 次后该用户不再展示(0 不限)')
    can_close: bool = Field(default=True, description='是否允许用户主动关闭')
    extra: dict | None = Field(None, description='形态特有字段兜底')


class UpdateSlotParam(SchemaBase):
    """更新运营位参数"""

    name: str | None = Field(None, max_length=128, description='内部名称')
    slot_type: str | None = Field(None, max_length=32, description='形态')
    scene: str | None = Field(None, max_length=64, description='触发场景')
    title: str | None = Field(None, max_length=255, description='标题')
    subtitle: str | None = Field(None, max_length=255, description='副标题')
    image_url: str | None = Field(None, max_length=500, description='主图 URL')
    detail: str | None = Field(None, description='富文本详情')
    jump_type: str | None = Field(None, max_length=32, description='跳转类型')
    jump_target: str | None = Field(None, max_length=500, description='跳转目标')
    jump_extra: dict | None = Field(None, description='扩展跳转参数')
    start_time: datetime | None = Field(None, description='投放开始时间')
    end_time: datetime | None = Field(None, description='投放结束时间')
    status: int | None = Field(None, ge=0, le=2, description='状态')
    priority: int | None = Field(None, description='优先级')
    target_user_type: int | None = Field(None, ge=0, le=99, description='目标用户类型')
    target_min_member_level: int | None = Field(None, ge=0, description='最低会员等级权重')
    target_extra: dict | None = Field(None, description='扩展分群条件')
    max_show_per_user: int | None = Field(None, ge=0, description='单用户终生最多展示次数')
    max_show_per_day_per_user: int | None = Field(None, ge=0, description='单用户每日最多展示次数')
    close_dismiss_count: int | None = Field(None, ge=0, description='关闭 N 次后不再展示')
    can_close: bool | None = Field(None, description='是否允许用户主动关闭')
    extra: dict | None = Field(None, description='扩展字段')


class GetSlotDetail(SchemaBase):
    """运营位详情(管理端)"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='运营位 ID')
    code: str = Field(description='业务码')
    name: str = Field(description='内部名称')
    slot_type: str = Field(description='形态')
    scene: str = Field(description='触发场景')
    title: str | None = Field(None, description='标题')
    subtitle: str | None = Field(None, description='副标题')
    image_url: str | None = Field(None, description='主图 URL')
    detail: str | None = Field(None, description='富文本详情')
    jump_type: str = Field(description='跳转类型')
    jump_target: str | None = Field(None, description='跳转目标')
    jump_extra: dict | None = Field(None, description='扩展跳转参数')
    start_time: datetime | None = Field(None, description='投放开始时间')
    end_time: datetime | None = Field(None, description='投放结束时间')
    status: int = Field(description='状态')
    priority: int = Field(description='优先级')
    target_user_type: int = Field(description='目标用户类型')
    target_min_member_level: int = Field(description='最低会员等级权重')
    target_extra: dict | None = Field(None, description='扩展分群条件')
    max_show_per_user: int = Field(description='单用户终生最多展示次数')
    max_show_per_day_per_user: int = Field(description='单用户每日最多展示次数')
    close_dismiss_count: int = Field(description='关闭 N 次后不再展示')
    can_close: bool = Field(description='是否允许用户主动关闭')
    extra: dict | None = Field(None, description='扩展字段')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetActiveSlot(SchemaBase):
    """命中的运营位(用户端简化输出)"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='运营位 ID')
    code: str = Field(description='业务码')
    slot_type: str = Field(description='形态')
    scene: str = Field(description='触发场景')
    title: str | None = Field(None, description='标题')
    subtitle: str | None = Field(None, description='副标题')
    image_url: str | None = Field(None, description='主图 URL')
    detail: str | None = Field(None, description='富文本详情')
    jump_type: str = Field(description='跳转类型')
    jump_target: str | None = Field(None, description='跳转目标')
    jump_extra: dict | None = Field(None, description='扩展跳转参数')
    can_close: bool = Field(description='是否允许关闭')
    priority: int = Field(description='优先级')
    extra: dict | None = Field(None, description='扩展字段')


# ============ 行为上报 ============
class ReportSlotActionParam(SchemaBase):
    """上报运营位行为参数"""

    action: int = Field(ge=0, le=2, description='行为类型(0 曝光 1 点击 2 关闭)')
    scene: str | None = Field(None, max_length=64, description='触发场景')


# ============ 数据统计 ============
class SlotStatsResult(SchemaBase):
    """运营位统计结果"""

    show_count: int = Field(description='曝光数')
    click_count: int = Field(description='点击数')
    close_count: int = Field(description='关闭数')
    ctr: float = Field(description='点击率(click/show)')
