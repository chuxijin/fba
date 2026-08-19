#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, model_validator

from backend.common.schema import SchemaBase

MemoryDeckScope = Literal['system', 'personal']
MemoryStatus = Literal['active', 'disabled', 'archived']
MemoryCardType = Literal['cloze', 'correction']
MemoryResponseMode = Literal['reveal', 'input', 'choice', 'select_replace']
MemoryRevisionStatus = Literal['draft', 'published', 'retired']


class MemoryTextSegmentParam(SchemaBase):
    """素材中的普通文本片段。"""

    type: Literal['text'] = 'text'
    text: str = Field(min_length=1, max_length=10000, description='普通文本')


class MemoryPointSegmentParam(SchemaBase):
    """素材中的记忆点，保存正确内容与错误内容。"""

    type: Literal['point'] = 'point'
    id: str = Field(min_length=1, max_length=32, description='记忆点稳定标识，如 p1')
    correct: str = Field(min_length=1, max_length=200, description='正确内容')
    wrong: str = Field(min_length=1, max_length=200, description='错误内容')
    options: list[str] = Field(
        default_factory=list,
        max_length=20,
        description='选择填空选项，空则自动使用正确/错误内容',
    )
    hint: str | None = Field(None, max_length=500, description='提示')


MemorySegmentParam = Annotated[
    MemoryTextSegmentParam | MemoryPointSegmentParam,
    Field(discriminator='type'),
]


class MemoryContentParam(SchemaBase):
    """卡片内容参数"""

    segments: list[MemorySegmentParam] = Field(min_length=1, max_length=100, description='完整素材分段')
    title: str | None = Field(None, max_length=255, description='卡片副标题')
    settings: dict[str, Any] = Field(
        default_factory=dict,
        description='展示配置，如 show_hint / shuffle_options',
    )

    @model_validator(mode='after')
    def validate_segments(self) -> 'MemoryContentParam':
        """至少包含一个记忆点，且记忆点标识唯一。"""
        points = [item for item in self.segments if isinstance(item, MemoryPointSegmentParam)]
        ids = [item.id for item in points]
        if not points:
            raise ValueError('至少需要一个记忆点')
        if len(ids) != len(set(ids)):
            raise ValueError('记忆点标识不能重复')
        if any(not item.id.startswith('p') for item in points):
            raise ValueError('记忆点标识必须以 p 开头，如 p1')
        if any(item.correct.strip() == item.wrong.strip() for item in points):
            raise ValueError('正确内容和错误内容不能相同')
        return self


class CreateDeckParam(SchemaBase):
    """创建记忆卡组参数"""

    name: str = Field(min_length=1, max_length=120, description='卡组名称')
    code: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$',
        description='稳定业务编码，空则自动生成',
    )
    description: str | None = Field(None, max_length=5000, description='卡组描述')
    category_id: int | None = Field(None, gt=0, description='所属领域分类 ID（考公/考研等）')
    scope: MemoryDeckScope = Field(default='system', description='system 公共 / personal 私人')
    status: MemoryStatus = Field(default='active', description='卡组状态')
    daily_new_limit: int = Field(default=20, ge=0, le=500, description='默认每日新卡上限')
    daily_review_limit: int = Field(default=200, ge=1, le=2000, description='默认每日复习上限')
    sort_order: int = Field(default=0, ge=0, description='排序')
    settings: dict[str, Any] = Field(default_factory=dict, description='扩展配置')


class UpdateDeckParam(SchemaBase):
    """更新记忆卡组参数"""

    name: str | None = Field(None, min_length=1, max_length=120, description='卡组名称')
    description: str | None = Field(None, max_length=5000, description='卡组描述')
    category_id: int | None = Field(None, gt=0, description='所属领域分类 ID（考公/考研等）')
    status: MemoryStatus | None = Field(None, description='卡组状态')
    daily_new_limit: int | None = Field(None, ge=0, le=500, description='默认每日新卡上限')
    daily_review_limit: int | None = Field(None, ge=1, le=2000, description='默认每日复习上限')
    sort_order: int | None = Field(None, ge=0, description='排序')
    settings: dict[str, Any] | None = Field(None, description='扩展配置')


class GetDeckDetail(SchemaBase):
    """记忆卡组详情"""

    id: int = Field(description='卡组 ID')
    code: str = Field(description='稳定业务编码')
    name: str = Field(description='卡组名称')
    description: str | None = Field(None, description='卡组描述')
    category_id: int | None = Field(None, description='所属领域分类 ID')
    scope: str = Field(description='system/personal')
    owner_id: int | None = Field(None, description='私人卡组所有者')
    status: str = Field(description='卡组状态')
    daily_new_limit: int = Field(description='默认每日新卡上限')
    daily_review_limit: int = Field(description='默认每日复习上限')
    sort_order: int = Field(description='排序')
    settings: dict[str, Any] = Field(default_factory=dict, description='扩展配置')
    card_count: int = Field(default=0, description='卡组内卡片数')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class CreateCardParam(SchemaBase):
    """创建记忆卡参数"""

    deck_id: int = Field(gt=0, description='卡组 ID')
    group_id: int | None = Field(None, gt=0, description='所属分组（章/节）ID，空为卡组根目录')
    code: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$',
        description='稳定业务编码，空则自动生成',
    )
    title: str = Field(min_length=1, max_length=255, description='卡片标题')
    card_type: MemoryCardType = Field(default='cloze', description='记忆玩法')
    response_mode: MemoryResponseMode = Field(default='input', description='作答交互')
    status: MemoryStatus = Field(default='active', description='卡片状态')
    sort_order: int = Field(default=0, ge=0, description='排序')
    content: MemoryContentParam = Field(description='卡片内容（首次创建即发布为版本 1）')


class UpdateCardParam(SchemaBase):
    """更新记忆卡参数"""

    title: str | None = Field(None, min_length=1, max_length=255, description='卡片标题')
    group_id: int | None = Field(None, gt=0, description='所属分组（章/节）ID，空为卡组根目录')
    card_type: MemoryCardType | None = Field(None, description='记忆玩法')
    response_mode: MemoryResponseMode | None = Field(None, description='作答交互')
    status: MemoryStatus | None = Field(None, description='卡片状态')
    sort_order: int | None = Field(None, ge=0, description='排序')
    content: MemoryContentParam | None = Field(None, description='新内容，传入则发布新版本')


class GetCardDetail(SchemaBase):
    """记忆卡详情"""

    id: int = Field(description='卡片 ID')
    deck_id: int = Field(description='卡组 ID')
    group_id: int | None = Field(None, description='所属分组 ID')
    group_name: str | None = Field(None, description='所属分组名称')
    deck_name: str | None = Field(None, description='卡组名称')
    code: str = Field(description='稳定业务编码')
    title: str = Field(description='卡片标题')
    card_type: str = Field(description='记忆玩法')
    response_mode: str = Field(description='作答交互')
    status: str = Field(description='卡片状态')
    sort_order: int = Field(description='排序')
    current_revision_id: int | None = Field(None, description='当前发布版本 ID')
    revision_no: int | None = Field(None, description='当前发布版本号')
    content: dict[str, Any] | None = Field(None, description='当前发布内容')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetCardListItem(SchemaBase):
    """记忆卡列表项"""

    id: int = Field(description='卡片 ID')
    deck_id: int = Field(description='卡组 ID')
    group_id: int | None = Field(None, description='所属分组 ID')
    group_name: str | None = Field(None, description='所属分组名称')
    code: str = Field(description='稳定业务编码')
    title: str = Field(description='卡片标题')
    card_type: str = Field(description='记忆玩法')
    response_mode: str = Field(description='作答交互')
    status: str = Field(description='卡片状态')
    revision_no: int | None = Field(None, description='当前发布版本号')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetReviewLogItem(SchemaBase):
    """复习日志列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='日志 ID')
    user_id: int = Field(description='用户 ID')
    card_id: int = Field(description='卡片 ID')
    revision_id: int | None = Field(None, description='版本 ID')
    rating: int = Field(description='评分 1-4')
    check_result: str = Field(description='客观判定')
    revealed: bool = Field(description='是否揭晓')
    duration_ms: int = Field(description='用时毫秒')
    next_due: datetime | None = Field(None, description='调度后到期时间')
    reviewed_at: datetime = Field(description='复习时间')


class CreateGroupParam(SchemaBase):
    """创建分组参数（章/节等目录）"""

    deck_id: int = Field(gt=0, description='卡组 ID')
    parent_id: int | None = Field(None, gt=0, description='父分组 ID，空为卡组一级分组')
    name: str = Field(min_length=1, max_length=120, description='分组名称（章/节）')
    sort_order: int = Field(default=0, ge=0, description='排序')
    status: MemoryStatus = Field(default='active', description='状态')


class UpdateGroupParam(SchemaBase):
    """更新分组参数"""

    name: str | None = Field(None, min_length=1, max_length=120, description='分组名称')
    parent_id: int | None = Field(None, gt=0, description='父分组 ID，空为一级分组')
    sort_order: int | None = Field(None, ge=0, description='排序')
    status: MemoryStatus | None = Field(None, description='状态')


class GetGroupDetail(SchemaBase):
    """分组详情"""

    id: int = Field(description='分组 ID')
    deck_id: int = Field(description='卡组 ID')
    parent_id: int | None = Field(None, description='父分组 ID')
    name: str = Field(description='分组名称')
    sort_order: int = Field(description='排序')
    status: str = Field(description='状态')
    card_count: int = Field(default=0, description='直接子卡片数')
    children: list['GetGroupDetail'] = Field(default_factory=list, description='子分组')
