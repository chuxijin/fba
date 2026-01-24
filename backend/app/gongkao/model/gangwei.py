#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, UserMixin, id_key


class GkGangwei(Base, UserMixin):
    """公考岗位表"""

    __tablename__ = 'gk_gangwei'
    __table_args__ = (
        sa.UniqueConstraint('year', 'org_region', 'position_code', name='uq_gangwei_year_region_position'),
        {'comment': '公考岗位表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    # 必填字段（无默认值）
    year: Mapped[int] = mapped_column(sa.Integer, index=True, comment='年度')
    position_code: Mapped[str] = mapped_column(sa.String(50), index=True, comment='职位代码')
    org_region: Mapped[str] = mapped_column(sa.String(100), index=True, comment='单位所属地区')

    # 基础信息（可选字段）
    serial_no: Mapped[str | None] = mapped_column(sa.String(50), default=None, comment='序号')
    org_code: Mapped[str | None] = mapped_column(sa.String(50), default=None, comment='单位代码')
    org_name: Mapped[str | None] = mapped_column(sa.String(200), default=None, index=True, comment='单位名称')
    position_name: Mapped[str | None] = mapped_column(sa.String(200), default=None, index=True, comment='职位名称')

    # 单位属性
    org_system: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='单位所属系统')
    org_level: Mapped[str | None] = mapped_column(sa.String(50), default=None, comment='单位层级')
    work_location: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='工作地点')

    # 职位属性
    job_rank: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='职级')
    exam_type: Mapped[str | None] = mapped_column(sa.String(50), default=None, comment='试卷类型')
    recruit_num: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='招收人数')
    recruit_scope: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='招考范围')

    # 报考要求
    age_requirement: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='年龄要求')
    gender_requirement: Mapped[str | None] = mapped_column(sa.String(50), default=None, comment='性别要求')
    ethnicity_requirement: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='民族要求')
    politics_requirement: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='政治面貌要求')
    education_requirement: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='文化程度要求')
    degree_requirement: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='学位要求')
    edu_type_requirement: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='学历类别要求')
    work_exp_requirement: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='工作经历要求')
    special_position: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='专门职位')
    major_requirement: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='所需专业')
    other_requirement: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='其他要求')

    # 其他信息
    position_intro: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='职位简介')
    contact: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='联系方式')
    remark: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='备注')

    # 报考统计
    apply_count: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='报名数')
    pass_count: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='审核通过')

    # 成绩统计
    written_min_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='笔试最低分')
    written_avg_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='笔试平均分')
    written_max_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='笔试最高分')
    interview_min_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='面试最低分')
    interview_avg_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='面试平均分')
    interview_max_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='面试最高分')
