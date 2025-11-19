#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UniversalText, id_key
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from .practice import PracticeRecord, PracticeSession, WrongQuestionBook


class UserAccount(Base):
    """用户账户表"""

    __tablename__ = 'study_user_account'

    id: Mapped[id_key] = mapped_column(init=False)
    username: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, comment='用户名')
    nickname: Mapped[str] = mapped_column(sa.String(64), comment='昵称')
    union_id: Mapped[str | None] = mapped_column(
        sa.String(128), default=None, unique=True, index=True, comment='微信 UnionID'
    )
    open_id: Mapped[str | None] = mapped_column(sa.String(128), default=None, index=True, comment='微信 OpenID')
    session_key: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='微信 SessionKey')
    avatar: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='头像')
    phone: Mapped[str | None] = mapped_column(sa.String(256), default=None, index=True, comment='手机号（加密）')
    email: Mapped[str | None] = mapped_column(sa.String(256), default=None, index=True, comment='邮箱')
    real_name: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='真实姓名（加密）')
    id_card: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='身份证号（加密）')
    gender: Mapped[int | None] = mapped_column(default=None, comment='性别（0 未知 1 男 2 女）')
    birthday: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='生日')
    province: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='省')
    city: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='市')
    district: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='区')
    education: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='学历')
    occupation: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='职业')
    school: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='学校')
    graduation_year: Mapped[int | None] = mapped_column(default=None, comment='毕业年份')
    target_exam: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='目标考试')
    identity: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='身份')
    status: Mapped[int] = mapped_column(default=1, index=True, comment='状态（0 停用 1 正常）')
    is_vip: Mapped[bool] = mapped_column(default=False, comment='是否 VIP')
    register_channel: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='注册渠道')
    channel_source: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='渠道来源')
    medium: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='媒介')
    campaign: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='活动标识')
    referrer_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='推荐人 ID')
    first_visit_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='首访时间')
    message_push_settings: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='消息推送设置 JSON')
    study_preference_settings: Mapped[str | None] = mapped_column(
        UniversalText, default=None, comment='刷题偏好设置 JSON'
    )
    privacy_settings: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='隐私设置 JSON')
    theme: Mapped[str] = mapped_column(sa.String(32), default='light', comment='主题')
    language: Mapped[str] = mapped_column(sa.String(16), default='zh_CN', comment='语言')
    profile_completion: Mapped[int] = mapped_column(default=0, comment='资料完成度（0-100）')
    register_time: Mapped[datetime] = mapped_column(TimeZone, init=False, default_factory=timezone.now, comment='注册时间')
    last_login_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近登录时间')
    last_active_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近活跃时间')

    addresses: Mapped[list[UserContactAddress]] = relationship(init=False, back_populates='user')
    memberships: Mapped[list[UserMembership]] = relationship(init=False, back_populates='user')
    devices: Mapped[list[UserDevice]] = relationship(init=False, back_populates='user')
    growth_points: Mapped[UserGrowthPoints | None] = relationship(init=False, back_populates='user', uselist=False)
    children_relations: Mapped[list[SpreadRelation]] = relationship(
        init=False, back_populates='parent_user', foreign_keys='SpreadRelation.parent_user_id'
    )
    parent_relations: Mapped[list[SpreadRelation]] = relationship(
        init=False, back_populates='child_user', foreign_keys='SpreadRelation.child_user_id'
    )
    commission: Mapped[UserCommission | None] = relationship(init=False, back_populates='user', uselist=False)
    blacklist_records: Mapped[list[UserBlacklist]] = relationship(init=False, back_populates='user')

    # ============ 练习刷题关系 ============
    practice_sessions: Mapped[list['PracticeSession']] = relationship(init=False, back_populates='user', lazy='noload')
    practice_records: Mapped[list['PracticeRecord']] = relationship(init=False, back_populates='user', lazy='noload')
    wrong_questions: Mapped[list['WrongQuestionBook']] = relationship(init=False, back_populates='user', lazy='noload')


class UserContactAddress(Base):
    """用户收货地址表"""

    __tablename__ = 'study_user_contact_address'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey('study_user_account.id', ondelete='CASCADE'), index=True, comment='用户 ID'
    )
    recipient_name: Mapped[str] = mapped_column(sa.String(64), comment='收货人姓名')
    recipient_phone: Mapped[str] = mapped_column(sa.String(256), comment='手机号（加密）')
    province: Mapped[str] = mapped_column(sa.String(64), comment='省')
    city: Mapped[str] = mapped_column(sa.String(64), comment='市')
    district: Mapped[str] = mapped_column(sa.String(64), comment='区')
    detail_address: Mapped[str] = mapped_column(sa.String(512), comment='详细地址')
    is_default: Mapped[bool] = mapped_column(default=False, comment='是否默认地址')
    address_label: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='地址标签')

    user: Mapped[UserAccount] = relationship(init=False, back_populates='addresses')


class UserMembership(Base):
    """用户会员权益表"""

    __tablename__ = 'study_user_membership'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey('study_user_account.id', ondelete='CASCADE'), index=True, comment='用户 ID'
    )
    category: Mapped[int] = mapped_column(index=True, comment='会员分类（0=全部 1=题库 2=词库 3=资料包 4=商城）')
    res_type: Mapped[str] = mapped_column(sa.String(32), comment='资源类型（category=整个分类 single=单个资源）')
    method: Mapped[str] = mapped_column(
        sa.String(32), comment='开通方式（solo=购买 group=拼团 code=激活码 manual=手动 package=套餐）'
    )
    start_time: Mapped[datetime] = mapped_column(TimeZone, comment='生效时间')
    end_time: Mapped[datetime] = mapped_column(TimeZone, index=True, comment='到期时间')
    res_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='资源 ID')
    res_name: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='资源名称')
    pkg_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='套餐 ID')
    pkg_name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='套餐名称')
    act_code: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='激活码')
    operator_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='操作人 ID')
    order_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='订单 ID')
    status: Mapped[int] = mapped_column(default=1, index=True, comment='状态（0 失效 1 有效）')
    auto_renew: Mapped[bool] = mapped_column(default=False, comment='自动续费')
    extra: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='扩展数据 JSON')

    user: Mapped[UserAccount] = relationship(init=False, back_populates='memberships')


class UserDevice(Base):
    """用户设备表"""

    __tablename__ = 'study_user_device'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey('study_user_account.id', ondelete='CASCADE'), index=True, comment='用户 ID'
    )
    device_id: Mapped[str] = mapped_column(sa.String(128), unique=True, index=True, comment='设备唯一标识')
    platform: Mapped[str] = mapped_column(sa.String(32), comment='平台（ios/android/h5/pc）')
    device_model: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='设备型号')
    os_version: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='操作系统版本')
    app_version: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='App 版本')
    push_token: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='推送 Token')
    last_login_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近登录时间')
    last_ip: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='最近 IP')
    last_city: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='最近城市')
    is_online: Mapped[bool] = mapped_column(default=False, comment='是否在线')

    user: Mapped[UserAccount] = relationship(init=False, back_populates='devices')


class UserGrowthPoints(Base):
    """用户成长积分表"""

    __tablename__ = 'study_user_growth_points'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey('study_user_account.id', ondelete='CASCADE'), unique=True, index=True, comment='用户 ID'
    )
    current_points: Mapped[int] = mapped_column(default=0, comment='当前积分')
    total_earned_points: Mapped[int] = mapped_column(default=0, comment='累计获取积分')
    total_consumed_points: Mapped[int] = mapped_column(default=0, comment='累计消耗积分')
    points_status: Mapped[int] = mapped_column(default=1, comment='积分状态（0 冻结 1 正常）')
    last_points_change_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近积分变动时间')
    current_growth_value: Mapped[int] = mapped_column(default=0, comment='当前成长值')
    level: Mapped[int] = mapped_column(default=1, comment='等级')
    total_experience: Mapped[int] = mapped_column(default=0, comment='累计经验值')
    last_task_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近任务时间')

    user: Mapped[UserAccount] = relationship(init=False, back_populates='growth_points')


class SpreadRelation(Base):
    """推广关系链表"""

    __tablename__ = 'study_spread_relation'

    id: Mapped[id_key] = mapped_column(init=False)
    parent_user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey('study_user_account.id', ondelete='CASCADE'), index=True, comment='推广人用户 ID'
    )
    child_user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey('study_user_account.id', ondelete='CASCADE'), index=True, comment='被推广用户 ID'
    )
    spread_type: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='推广类型（share/group/agent）')
    node_depth: Mapped[int] = mapped_column(default=1, comment='推广层级深度')
    bind_time: Mapped[datetime] = mapped_column(TimeZone, init=False, default_factory=timezone.now, comment='绑定时间')

    parent_user: Mapped[UserAccount] = relationship(
        init=False, back_populates='children_relations', foreign_keys=[parent_user_id]
    )
    child_user: Mapped[UserAccount] = relationship(
        init=False, back_populates='parent_relations', foreign_keys=[child_user_id]
    )


class UserCommission(Base):
    """用户分销佣金表"""

    __tablename__ = 'study_user_commission'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey('study_user_account.id', ondelete='CASCADE'), unique=True, index=True, comment='用户 ID'
    )
    total_commission: Mapped[float] = mapped_column(sa.Numeric(10, 2), default=0.00, comment='累计佣金（元）')
    available_commission: Mapped[float] = mapped_column(sa.Numeric(10, 2), default=0.00, comment='可提现佣金（元）')
    frozen_commission: Mapped[float] = mapped_column(sa.Numeric(10, 2), default=0.00, comment='冻结佣金（元）')
    withdrawn_commission: Mapped[float] = mapped_column(sa.Numeric(10, 2), default=0.00, comment='已提现佣金（元）')
    commission_rate: Mapped[float] = mapped_column(sa.Numeric(5, 2), default=10.00, comment='佣金比例（%）')
    agent_level: Mapped[int] = mapped_column(default=1, comment='代理等级')
    total_promoted_users: Mapped[int] = mapped_column(default=0, comment='累计推广用户数')
    total_orders: Mapped[int] = mapped_column(default=0, comment='累计订单数')
    last_commission_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近佣金时间')
    withdrawal_records: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='提现记录 JSON')

    user: Mapped[UserAccount] = relationship(init=False, back_populates='commission')


class UserBlacklist(Base):
    """用户黑名单表"""

    __tablename__ = 'study_user_blacklist'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey('study_user_account.id', ondelete='CASCADE'), index=True, comment='用户 ID'
    )
    ban_time: Mapped[datetime] = mapped_column(TimeZone, comment='封禁时间')
    ban_reason: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='封禁原因')
    ban_type: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='封禁类型（temp/permanent）')
    unban_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='解除时间')
    operator_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='操作人 ID')
    remark: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='备注')
    status: Mapped[int] = mapped_column(default=1, index=True, comment='状态（0 已解除 1 封禁中）')

    user: Mapped[UserAccount] = relationship(init=False, back_populates='blacklist_records')
