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
        sa.Index('ix_gangwei_year_region', 'year', 'region'),
        sa.Index('ix_gangwei_dept_position', 'dept_name', 'position_name'),
        {'comment': '公考岗位表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    # ========== 基础标识 (必填字段放前面) ==========
    year: Mapped[int] = mapped_column(sa.Integer, index=True, comment='年度')

    # ========== 基础标识 (可选) ==========
    position_code: Mapped[str | None] = mapped_column(sa.String(50), default=None, index=True, comment='职位代码')
    serial_no: Mapped[str | None] = mapped_column(sa.String(50), default=None, comment='序号')

    # ========== 部门信息 ==========
    dept_code: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='部门代码')
    dept_name: Mapped[str | None] = mapped_column(sa.String(300), default=None, index=True, comment='部门名称')
    bureau: Mapped[str | None] = mapped_column(sa.String(300), default=None, comment='用人司局')
    org_nature: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='机构性质')
    org_level: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='机构层级')
    dept_website: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='部门网站')

    # ========== 职位信息 ==========
    position_name: Mapped[str | None] = mapped_column(sa.String(300), default=None, index=True, comment='职位名称')
    position_attr: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='职位属性')
    position_intro: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='职位简介')
    recruit_num: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='招考人数')
    recruit_scope: Mapped[str | None] = mapped_column(sa.String(300), default=None, comment='招考范围')
    exam_category: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='考试类别')
    job_rank: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='职级')

    # ========== 报考条件 ==========
    major: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='专业')
    education: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='学历')
    degree: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='学位')
    edu_type: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='学历类别')
    politics: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='政治面貌')
    age_requirement: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='年龄要求')
    gender_requirement: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='性别要求')
    ethnicity_requirement: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='民族要求')
    grassroots_years: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='基层工作年限')
    grassroots_project: Mapped[str | None] = mapped_column(sa.String(300), default=None, comment='服务基层项目')
    special_position: Mapped[str | None] = mapped_column(sa.String(300), default=None, comment='专门职位')
    other_requirement: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='其他条件')

    # ========== 地点信息 ==========
    region: Mapped[str | None] = mapped_column(sa.String(200), default=None, index=True, comment='所属地区')
    work_location: Mapped[str | None] = mapped_column(sa.String(300), default=None, comment='工作地点')
    settlement_location: Mapped[str | None] = mapped_column(sa.String(300), default=None, comment='落户地点')

    # ========== 面试相关 ==========
    interview_ratio: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='面试比例')
    has_professional_test: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='是否专业测试')

    # ========== 联系方式 ==========
    phone1: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='咨询电话1')
    phone2: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='咨询电话2')
    phone3: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='咨询电话3')
    remark: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='备注')

    # ========== 统计字段 ==========
    exam_type: Mapped[str | None] = mapped_column(sa.String(100), default=None, index=True, comment='考试类型')
    apply_count: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='报名人数')
    pass_count: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='审核通过')
    competition_ratio: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='竞争比')
    written_min_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='笔试最低分')
    written_avg_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='笔试平均分')
    written_max_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='笔试最高分')
    interview_min_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='面试最低分')
    interview_avg_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='面试平均分')
    interview_max_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='面试最高分')
