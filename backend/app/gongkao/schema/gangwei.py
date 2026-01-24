#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class GangweiSchemaBase(SchemaBase):
    """岗位基础"""

    year: int = Field(..., description='年度')
    serial_no: str | None = Field(None, description='序号')
    org_code: str | None = Field(None, description='单位代码')
    org_name: str | None = Field(None, description='单位名称')
    position_code: str = Field(..., description='职位代码')
    position_name: str | None = Field(None, description='职位名称')

    # 单位属性
    org_system: str | None = Field(None, description='单位所属系统')
    org_region: str = Field(..., description='单位所属地区')
    org_level: str | None = Field(None, description='单位层级')
    work_location: str | None = Field(None, description='工作地点')

    # 职位属性
    job_rank: str | None = Field(None, description='职级')
    exam_type: str | None = Field(None, description='试卷类型')
    recruit_num: int | None = Field(None, description='招收人数')
    recruit_scope: str | None = Field(None, description='招考范围')

    # 报考要求
    age_requirement: str | None = Field(None, description='年龄要求')
    gender_requirement: str | None = Field(None, description='性别要求')
    ethnicity_requirement: str | None = Field(None, description='民族要求')
    politics_requirement: str | None = Field(None, description='政治面貌要求')
    education_requirement: str | None = Field(None, description='文化程度要求')
    degree_requirement: str | None = Field(None, description='学位要求')
    edu_type_requirement: str | None = Field(None, description='学历类别要求')
    work_exp_requirement: str | None = Field(None, description='工作经历要求')
    special_position: str | None = Field(None, description='专门职位')
    major_requirement: str | None = Field(None, description='所需专业')
    other_requirement: str | None = Field(None, description='其他要求')

    # 其他信息
    position_intro: str | None = Field(None, description='职位简介')
    contact: str | None = Field(None, description='联系方式')
    remark: str | None = Field(None, description='备注')

    # 报考统计
    apply_count: int | None = Field(None, description='报名数')
    pass_count: int | None = Field(None, description='审核通过')

    # 成绩统计
    written_min_score: Decimal | None = Field(None, description='笔试最低分')
    written_avg_score: Decimal | None = Field(None, description='笔试平均分')
    written_max_score: Decimal | None = Field(None, description='笔试最高分')
    interview_min_score: Decimal | None = Field(None, description='面试最低分')
    interview_avg_score: Decimal | None = Field(None, description='面试平均分')
    interview_max_score: Decimal | None = Field(None, description='面试最高分')


class GangweiParam(SchemaBase):
    """岗位查询参数"""

    year: int | None = Field(None, description='年度')
    org_name: str | None = Field(None, description='单位名称')
    org_region: str | None = Field(None, description='单位所属地区')
    position_name: str | None = Field(None, description='职位名称')
    position_code: str | None = Field(None, description='职位代码')


class CreateGangweiParam(GangweiSchemaBase):
    """创建岗位参数"""


class UpdateGangweiParam(SchemaBase):
    """更新岗位参数"""

    year: int | None = Field(None, description='年度')
    serial_no: str | None = Field(None, description='序号')
    org_code: str | None = Field(None, description='单位代码')
    org_name: str | None = Field(None, description='单位名称')
    position_code: str | None = Field(None, description='职位代码')
    position_name: str | None = Field(None, description='职位名称')
    org_system: str | None = Field(None, description='单位所属系统')
    org_region: str | None = Field(None, description='单位所属地区')
    org_level: str | None = Field(None, description='单位层级')
    work_location: str | None = Field(None, description='工作地点')
    job_rank: str | None = Field(None, description='职级')
    exam_type: str | None = Field(None, description='试卷类型')
    recruit_num: int | None = Field(None, description='招收人数')
    recruit_scope: str | None = Field(None, description='招考范围')
    age_requirement: str | None = Field(None, description='年龄要求')
    gender_requirement: str | None = Field(None, description='性别要求')
    ethnicity_requirement: str | None = Field(None, description='民族要求')
    politics_requirement: str | None = Field(None, description='政治面貌要求')
    education_requirement: str | None = Field(None, description='文化程度要求')
    degree_requirement: str | None = Field(None, description='学位要求')
    edu_type_requirement: str | None = Field(None, description='学历类别要求')
    work_exp_requirement: str | None = Field(None, description='工作经历要求')
    special_position: str | None = Field(None, description='专门职位')
    major_requirement: str | None = Field(None, description='所需专业')
    other_requirement: str | None = Field(None, description='其他要求')
    position_intro: str | None = Field(None, description='职位简介')
    contact: str | None = Field(None, description='联系方式')
    remark: str | None = Field(None, description='备注')
    apply_count: int | None = Field(None, description='报名数')
    pass_count: int | None = Field(None, description='审核通过')
    written_min_score: Decimal | None = Field(None, description='笔试最低分')
    written_avg_score: Decimal | None = Field(None, description='笔试平均分')
    written_max_score: Decimal | None = Field(None, description='笔试最高分')
    interview_min_score: Decimal | None = Field(None, description='面试最低分')
    interview_avg_score: Decimal | None = Field(None, description='面试平均分')
    interview_max_score: Decimal | None = Field(None, description='面试最高分')


class DeleteGangweiParam(SchemaBase):
    """删除岗位参数"""

    ids: list[int] = Field(description='岗位 ID 列表')


class GetGangweiDetail(GangweiSchemaBase):
    """岗位详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='岗位 ID')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class ImportGangweiItem(SchemaBase):
    """导入岗位单条数据"""

    year: int = Field(..., alias='年度', description='年度')
    serial_no: str | None = Field(None, alias='序号', description='序号')
    org_code: str | None = Field(None, alias='单位代码', description='单位代码')
    org_name: str | None = Field(None, alias='单位名称', description='单位名称')
    position_code: str = Field(..., alias='职位代码', description='职位代码')
    position_name: str | None = Field(None, alias='职位名称', description='职位名称')
    org_system: str | None = Field(None, alias='单位所属系统', description='单位所属系统')
    org_region: str = Field(..., alias='单位所属地区', description='单位所属地区')
    org_level: str | None = Field(None, alias='单位层级', description='单位层级')
    work_location: str | None = Field(None, alias='工作地点', description='工作地点')
    job_rank: str | None = Field(None, alias='职级', description='职级')
    exam_type: str | None = Field(None, alias='试卷类型', description='试卷类型')
    recruit_num: int | None = Field(None, alias='招收人数', description='招收人数')
    recruit_scope: str | None = Field(None, alias='招考范围', description='招考范围')
    age_requirement: str | None = Field(None, alias='年龄要求', description='年龄要求')
    gender_requirement: str | None = Field(None, alias='性别要求', description='性别要求')
    ethnicity_requirement: str | None = Field(None, alias='民族要求', description='民族要求')
    politics_requirement: str | None = Field(None, alias='政治面貌要求', description='政治面貌要求')
    education_requirement: str | None = Field(None, alias='文化程度要求', description='文化程度要求')
    degree_requirement: str | None = Field(None, alias='学位要求', description='学位要求')
    edu_type_requirement: str | None = Field(None, alias='学历类别要求', description='学历类别要求')
    work_exp_requirement: str | None = Field(None, alias='工作经历要求', description='工作经历要求')
    special_position: str | None = Field(None, alias='专门职位', description='专门职位')
    major_requirement: str | None = Field(None, alias='所需专业', description='所需专业')
    position_intro: str | None = Field(None, alias='职位简介', description='职位简介')
    remark: str | None = Field(None, alias='备注', description='备注')
    contact: str | None = Field(None, alias='联系方式', description='联系方式')
    other_requirement: str | None = Field(None, alias='其他要求', description='其他要求')
    apply_count: int | None = Field(None, alias='报名数', description='报名数')
    pass_count: int | None = Field(None, alias='审核通过', description='审核通过')
    written_min_score: Decimal | None = Field(None, alias='笔试最低分', description='笔试最低分')
    written_avg_score: Decimal | None = Field(None, alias='笔试平均分', description='笔试平均分')
    written_max_score: Decimal | None = Field(None, alias='笔试最高分', description='笔试最高分')
    interview_min_score: Decimal | None = Field(None, alias='面试最低分', description='面试最低分')
    interview_avg_score: Decimal | None = Field(None, alias='面试平均分', description='面试平均分')
    interview_max_score: Decimal | None = Field(None, alias='面试最高分', description='面试最高分')


class ImportGangweiResult(SchemaBase):
    """导入岗位结果"""

    total: int = Field(description='总条数')
    success: int = Field(description='成功条数')
    failed: int = Field(description='失败条数')
    errors: list[str] = Field(default_factory=list, description='错误信息列表')
