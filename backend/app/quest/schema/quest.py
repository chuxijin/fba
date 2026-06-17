#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ============ 任务 ============
class CreateQuestParam(SchemaBase):
    """创建任务参数"""

    code: str = Field(min_length=1, max_length=64, description='任务码')
    quest_type: str = Field(default='manual', max_length=16, description='任务类型(manual 手动领取/auto 事件自动触发)')
    name: str = Field(min_length=1, max_length=128, description='任务名称')
    brief: str = Field(min_length=1, max_length=255, description='任务简介')
    info: str | None = Field(None, max_length=500, description='任务信息')
    detail: str | None = Field(None, description='任务详情')
    cover_image: str | None = Field(None, max_length=500, description='封面图 URL')
    start_time: datetime | None = Field(None, description='开始时间')
    end_time: datetime | None = Field(None, description='结束时间')
    status: int = Field(default=0, ge=0, le=3, description='状态(0 草稿 1 进行中 2 已暂停 3 已结束)')
    total_quota: int = Field(default=0, ge=0, description='总名额(0 不限)')
    max_claims_per_user: int = Field(default=1, ge=0, description='单用户最大领取次数(0表示不限)')
    claim_expire_seconds: int = Field(default=0, ge=0, description='领取后完成期限秒数(0 不限)')
    submission_required: bool = Field(default=True, description='是否需要提交内容')
    require_note: bool = Field(default=False, description='是否必填文字')
    require_image: bool = Field(default=False, description='是否必填图片')
    require_link: bool = Field(default=False, description='是否必填链接')
    review_required: bool = Field(default=True, description='是否需要人工审核')
    review_strategy: str = Field(default='manual', max_length=64, description='审核策略')
    submission_schema: dict | None = Field(None, description='结构化提交字段配置')
    reward_type: str = Field(default='points', max_length=32, description='奖励类型(vip/points/feature)')
    reward_data: dict | None = Field(None, description='奖励数据')
    trigger_type: str | None = Field(None, max_length=64, description='自动触发类型(空=人工领取)')
    trigger_target: int = Field(default=0, ge=0, description='自动触发达成阈值(0 当 trigger_type 为空时无意义)')
    trigger_payload: dict | None = Field(None, description='自动触发匹配条件(预留)')
    sort: int = Field(default=0, description='排序(数字越小越靠前)')
    domain_codes: list[str] | None = Field(None, description='关联领域码列表(空=全部领域可见)')


class UpdateQuestParam(SchemaBase):
    """更新任务参数"""

    name: str | None = Field(None, max_length=128, description='任务名称')
    quest_type: str | None = Field(None, max_length=16, description='任务类型(manual 手动领取/auto 事件自动触发)')
    brief: str | None = Field(None, max_length=255, description='任务简介')
    info: str | None = Field(None, max_length=500, description='任务信息')
    detail: str | None = Field(None, description='任务详情')
    cover_image: str | None = Field(None, max_length=500, description='封面图 URL')
    start_time: datetime | None = Field(None, description='开始时间')
    end_time: datetime | None = Field(None, description='结束时间')
    status: int | None = Field(None, ge=0, le=3, description='状态')
    total_quota: int | None = Field(None, ge=0, description='总名额')
    max_claims_per_user: int | None = Field(None, ge=0, description='单用户最大领取次数(0表示不限)')
    claim_expire_seconds: int | None = Field(None, ge=0, description='领取后完成期限秒数(0 不限)')
    submission_required: bool | None = Field(None, description='是否需要提交内容')
    require_note: bool | None = Field(None, description='是否必填文字')
    require_image: bool | None = Field(None, description='是否必填图片')
    require_link: bool | None = Field(None, description='是否必填链接')
    review_required: bool | None = Field(None, description='是否需要人工审核')
    review_strategy: str | None = Field(None, max_length=64, description='审核策略')
    submission_schema: dict | None = Field(None, description='结构化提交字段配置')
    reward_type: str | None = Field(None, max_length=32, description='奖励类型')
    reward_data: dict | None = Field(None, description='奖励数据')
    trigger_type: str | None = Field(None, max_length=64, description='自动触发类型(空=人工领取)')
    trigger_target: int | None = Field(None, ge=0, description='自动触发达成阈值')
    trigger_payload: dict | None = Field(None, description='自动触发匹配条件(预留)')
    sort: int | None = Field(None, description='排序')
    domain_codes: list[str] | None = Field(None, description='关联领域码列表(空=全部领域可见)')


class GetQuestDetail(SchemaBase):
    """任务详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='任务 ID')
    code: str = Field(description='任务码')
    quest_type: str = Field(description='任务类型')
    name: str = Field(description='任务名称')
    brief: str = Field(description='任务简介')
    info: str | None = Field(None, description='任务信息')
    detail: str | None = Field(None, description='任务详情')
    cover_image: str | None = Field(None, description='封面图 URL')
    start_time: datetime | None = Field(None, description='开始时间')
    end_time: datetime | None = Field(None, description='结束时间')
    status: int = Field(description='状态')
    total_quota: int = Field(description='总名额')
    claimed_count: int = Field(description='已领取数')
    max_claims_per_user: int = Field(description='单用户最大领取次数')
    claim_expire_seconds: int = Field(description='领取后完成期限秒数(0 不限)')
    submission_required: bool = Field(description='是否需要提交内容')
    require_note: bool = Field(description='是否必填文字')
    require_image: bool = Field(description='是否必填图片')
    require_link: bool = Field(description='是否必填链接')
    review_required: bool = Field(description='是否需要人工审核')
    review_strategy: str = Field(description='审核策略')
    submission_schema: dict | None = Field(None, description='结构化提交字段配置')
    reward_type: str = Field(description='奖励类型')
    reward_data: dict | None = Field(None, description='奖励数据')
    trigger_type: str | None = Field(None, description='自动触发类型(空=人工领取)')
    trigger_target: int = Field(description='自动触发达成阈值')
    trigger_payload: dict | None = Field(None, description='自动触发匹配条件')
    sort: int = Field(description='排序')
    domain_codes: list[str] | None = Field(None, description='关联领域码列表(空=全部领域可见)')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetQuestWithUserDetail(GetQuestDetail):
    """任务详情(含当前用户参与状态)"""

    my_claim_count: int = Field(default=0, description='当前用户已领取次数')
    my_active_claim_id: int | None = Field(None, description='当前用户进行中的领取 ID')
    my_latest_claim_status: int | None = Field(None, description='当前用户最近一次领取状态')
    my_current_progress: int = Field(default=0, description='当前用户在该任务的累计进度')


# ============ 领取/提交 ============
class SubmitClaimParam(SchemaBase):
    """提交任务内容参数"""

    submission_links: list[str] | None = Field(None, description='提交链接列表')
    submission_images: list[str] | None = Field(None, description='提交图片列表')
    submission_data: dict | None = Field(None, description='结构化提交数据')
    submission_note: str | None = Field(None, description='提交说明')


class GetClaimDetail(SchemaBase):
    """领取记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='领取记录 ID')
    quest_id: int = Field(description='任务 ID')
    user_id: int = Field(description='用户 ID')
    claim_status: int = Field(description='领取状态')
    claim_time: datetime | None = Field(None, description='领取时间')
    expire_time: datetime | None = Field(None, description='领取过期时间')
    submission_links: list[str] | None = Field(None, description='提交链接列表')
    submission_images: list[str] | None = Field(None, description='提交图片列表')
    submission_data: dict | None = Field(None, description='结构化提交数据')
    submission_note: str | None = Field(None, description='提交说明')
    submit_time: datetime | None = Field(None, description='提交时间')
    review_remark: str | None = Field(None, description='审核备注')
    reviewed_by: int | None = Field(None, description='审核人用户 ID')
    review_time: datetime | None = Field(None, description='审核时间')
    reward_status: int = Field(description='奖励状态')
    granted_at: datetime | None = Field(None, description='奖励发放时间')
    progress: int = Field(default=0, description='当前累计进度(自动触发型任务)')
    created_time: datetime = Field(description='创建时间')


# ============ 审核 ============
class ReviewClaimParam(SchemaBase):
    """审核领取记录参数"""

    decision: str = Field(pattern=r'^(approve|reject)$', description='审核决定(approve/reject)')
    remark: str | None = Field(None, max_length=500, description='审核备注')


class ReviewClaimResult(SchemaBase):
    """审核结果"""

    claim_id: int = Field(description='领取记录 ID')
    claim_status: int = Field(description='更新后的领取状态')
    reward_granted: bool = Field(description='奖励是否已发放')
    message: str = Field(description='结果提示')


class RevokeClaimParam(SchemaBase):
    """撤销审核参数"""

    remark: str | None = Field(None, max_length=500, description='撤销原因')


class RevokeClaimResult(SchemaBase):
    """撤销结果"""

    claim_id: int = Field(description='领取记录 ID')
    claim_status: int = Field(description='更新后的领取状态')
    reward_revoked: bool = Field(description='奖励是否已成功撤销')
    message: str = Field(description='结果提示')
