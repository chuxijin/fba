#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UniversalText, id_key


class GkUserProfile(Base):
    """用户画像主表"""

    __tablename__ = 'gk_user_profile'
    __table_args__ = (
        sa.UniqueConstraint('user_id', name='uq_user_profile_user_id'),
        {'comment': '用户画像主表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    # 关联用户
    user_id: Mapped[int] = mapped_column(sa.Integer, index=True, comment='关联用户ID')

    # ========== 基本信息 ==========
    birth_date: Mapped[date | None] = mapped_column(sa.Date, default=None, comment='出生日期')
    gender: Mapped[str | None] = mapped_column(sa.String(10), default=None, comment='性别')
    ethnicity: Mapped[str | None] = mapped_column(sa.String(50), default=None, comment='民族')
    hukou_region_code: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='户籍地区代码')
    origin_region_code: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='生源地代码')
    politics: Mapped[str | None] = mapped_column(sa.String(50), default=None, comment='政治面貌')

    # ========== 特殊身份 ==========
    special_identity: Mapped[str | None] = mapped_column(
        sa.String(200),
        default=None,
        comment='特殊身份: 退役军人/残疾人/烈士子女等，多个用逗号分隔',
    )

    # ========== 应届生状态 ==========
    is_fresh_graduate: Mapped[bool] = mapped_column(sa.Boolean, default=False, comment='是否为择业期应届生')

    # ========== 工作年限 ==========
    total_work_years: Mapped[int] = mapped_column(sa.Integer, default=0, comment='总工作年限（月）')

    # ========== 关联子表 ==========
    educations: Mapped[list[GkUserEducation]] = relationship(
        back_populates='profile',
        cascade='all, delete-orphan',
        lazy='selectin',
        default_factory=list,
        init=False,
    )
    region_preferences: Mapped[list[GkUserRegionPreference]] = relationship(
        back_populates='profile',
        cascade='all, delete-orphan',
        lazy='selectin',
        default_factory=list,
        init=False,
    )
    certificates: Mapped[list[GkUserCertificate]] = relationship(
        back_populates='profile',
        cascade='all, delete-orphan',
        lazy='selectin',
        default_factory=list,
        init=False,
    )
    work_experiences: Mapped[list[GkUserWorkExperience]] = relationship(
        back_populates='profile',
        cascade='all, delete-orphan',
        lazy='selectin',
        default_factory=list,
        init=False,
    )
    honors: Mapped[list[GkUserHonor]] = relationship(
        back_populates='profile',
        cascade='all, delete-orphan',
        lazy='selectin',
        default_factory=list,
        init=False,
    )


class GkUserEducation(Base):
    """用户教育经历表"""

    __tablename__ = 'gk_user_education'
    __table_args__ = (
        sa.Index('ix_user_education_profile', 'profile_id'),
        {'comment': '用户教育经历表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    # 关联用户画像
    profile_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey('gk_user_profile.id'), comment='画像ID')

    # ========== 学历信息 ==========
    edu_level: Mapped[str] = mapped_column(sa.String(50), comment='学历层次: 专科/本科/硕士研究生/博士研究生')
    degree: Mapped[str | None] = mapped_column(sa.String(50), default=None, comment='学位: 学士/硕士/博士')
    edu_type: Mapped[str] = mapped_column(
        sa.String(50),
        default='全日制',
        comment='学历性质: 全日制/非全日制',
    )

    # ========== 专业信息 ==========
    major_code: Mapped[str | None] = mapped_column(sa.String(20), default=None, index=True, comment='专业代码')
    major_name: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='专业名称')
    major_category: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='专业类')
    major_discipline: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='学科门类')

    # ========== 院校信息 ==========
    school_name: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='毕业院校')
    school_type: Mapped[str | None] = mapped_column(
        sa.String(100),
        default=None,
        comment='院校类型: 985/211/双一流/普通本科/专科',
    )
    enrollment_batch: Mapped[str | None] = mapped_column(
        sa.String(50),
        default=None,
        comment='招生批次: 本科一批/本科二批/专科批',
    )

    # ========== 时间信息 ==========
    start_date: Mapped[date | None] = mapped_column(sa.Date, default=None, comment='入学时间')
    end_date: Mapped[date | None] = mapped_column(sa.Date, default=None, comment='毕业时间')
    is_highest: Mapped[bool] = mapped_column(sa.Boolean, default=False, comment='是否最高学历')

    # 关联
    profile: Mapped[GkUserProfile] = relationship(back_populates='educations', init=False)


class GkUserRegionPreference(Base):
    """用户地区偏好表"""

    __tablename__ = 'gk_user_region_preference'
    __table_args__ = (
        sa.Index('ix_user_region_pref_profile', 'profile_id'),
        {'comment': '用户地区偏好表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    # 关联用户画像
    profile_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey('gk_user_profile.id'), comment='画像ID')

    # 地区信息（可精确到县）
    province_code: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='省代码')
    city_code: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='市代码')
    county_code: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='县/区代码')

    # 偏好设置
    priority: Mapped[int] = mapped_column(sa.Integer, default=1, comment='优先级: 1最高')
    include_sub_regions: Mapped[bool] = mapped_column(sa.Boolean, default=True, comment='是否包含下级区域')
    accept_remote_area: Mapped[bool] = mapped_column(sa.Boolean, default=False, comment='是否接受艰苦边远')

    # 关联
    profile: Mapped[GkUserProfile] = relationship(back_populates='region_preferences', init=False)


class GkUserCertificate(Base):
    """用户资格证书表"""

    __tablename__ = 'gk_user_certificate'
    __table_args__ = (
        sa.Index('ix_user_certificate_profile', 'profile_id'),
        {'comment': '用户资格证书表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    # 关联用户画像
    profile_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey('gk_user_profile.id'), comment='画像ID')

    # 证书信息
    cert_type: Mapped[str] = mapped_column(sa.String(100), comment='证书类型: 职业资格/专业技术/语言能力')
    cert_name: Mapped[str] = mapped_column(sa.String(200), comment='证书名称')
    cert_level: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='证书等级')
    cert_no: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='证书编号')
    issue_date: Mapped[date | None] = mapped_column(sa.Date, default=None, comment='取得时间')
    expire_date: Mapped[date | None] = mapped_column(sa.Date, default=None, comment='有效期至')

    # 关联
    profile: Mapped[GkUserProfile] = relationship(back_populates='certificates', init=False)


class GkUserWorkExperience(Base):
    """用户工作经历表"""

    __tablename__ = 'gk_user_work_experience'
    __table_args__ = (
        sa.Index('ix_user_work_exp_profile', 'profile_id'),
        {'comment': '用户工作经历表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    # 关联用户画像
    profile_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey('gk_user_profile.id'), comment='画像ID')

    # 单位信息
    company_name: Mapped[str] = mapped_column(sa.String(200), comment='单位名称')
    company_type: Mapped[str | None] = mapped_column(
        sa.String(100),
        default=None,
        comment='单位性质: 党政机关/事业单位/国企/民企/外企',
    )
    position: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='岗位名称')
    department: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='部门')

    # 时间
    start_date: Mapped[date | None] = mapped_column(sa.Date, default=None, comment='开始时间')
    end_date: Mapped[date | None] = mapped_column(sa.Date, default=None, comment='结束时间')
    is_current: Mapped[bool] = mapped_column(sa.Boolean, default=False, comment='是否当前工作')

    # 基层相关
    is_grassroots: Mapped[bool] = mapped_column(sa.Boolean, default=False, comment='是否基层工作经历')
    grassroots_project: Mapped[str | None] = mapped_column(
        sa.String(100),
        default=None,
        comment='服务基层项目: 三支一扶/西部计划/特岗教师/大学生村官',
    )
    service_region_code: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='服务地区代码')

    # 工作描述
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='工作描述')

    # 关联
    profile: Mapped[GkUserProfile] = relationship(back_populates='work_experiences', init=False)


class GkUserHonor(Base):
    """用户荣誉成就表"""

    __tablename__ = 'gk_user_honor'
    __table_args__ = (
        sa.Index('ix_user_honor_profile', 'profile_id'),
        {'comment': '用户荣誉成就表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    # 关联用户画像
    profile_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey('gk_user_profile.id'), comment='画像ID')

    # 荣誉信息
    honor_type: Mapped[str] = mapped_column(
        sa.String(100),
        comment='荣誉类型: 党员荣誉/学术荣誉/技能竞赛/社会实践',
    )
    honor_name: Mapped[str] = mapped_column(sa.String(200), comment='荣誉名称')
    honor_level: Mapped[str | None] = mapped_column(
        sa.String(100),
        default=None,
        comment='荣誉级别: 国家级/省级/市级/校级',
    )
    issue_org: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='颁发机构')
    issue_date: Mapped[date | None] = mapped_column(sa.Date, default=None, comment='取得时间')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='荣誉说明')

    # 关联
    profile: Mapped[GkUserProfile] = relationship(back_populates='honors', init=False)
