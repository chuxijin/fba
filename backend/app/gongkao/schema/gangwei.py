#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class GangweiSchemaBase(SchemaBase):
    """岗位基础"""

    # 基础标识
    year: int = Field(..., description='年度')
    position_code: str | None = Field(None, description='职位代码')
    serial_no: str | None = Field(None, description='序号')

    # 部门信息
    dept_code: str | None = Field(None, description='部门代码')
    dept_name: str | None = Field(None, description='部门名称')
    bureau: str | None = Field(None, description='用人司局')
    org_nature: str | None = Field(None, description='机构性质')
    org_level: str | None = Field(None, description='机构层级')
    dept_website: str | None = Field(None, description='部门网站')

    # 职位信息
    position_name: str | None = Field(None, description='职位名称')
    position_attr: str | None = Field(None, description='职位属性')
    position_intro: str | None = Field(None, description='职位简介')
    recruit_num: int | None = Field(None, description='招考人数')
    recruit_scope: str | None = Field(None, description='招考范围')
    exam_category: str | None = Field(None, description='考试类别')
    job_rank: str | None = Field(None, description='职级')

    # 报考条件
    major: str | None = Field(None, description='专业')
    education: str | None = Field(None, description='学历')
    degree: str | None = Field(None, description='学位')
    edu_type: str | None = Field(None, description='学历类别')
    politics: str | None = Field(None, description='政治面貌')
    age_requirement: str | None = Field(None, description='年龄要求')
    gender_requirement: str | None = Field(None, description='性别要求')
    ethnicity_requirement: str | None = Field(None, description='民族要求')
    grassroots_years: str | None = Field(None, description='基层工作年限')
    grassroots_project: str | None = Field(None, description='服务基层项目')
    special_position: str | None = Field(None, description='专门职位')
    other_requirement: str | None = Field(None, description='其他条件')

    # 地点信息
    region: str | None = Field(None, description='所属地区')
    work_location: str | None = Field(None, description='工作地点')
    settlement_location: str | None = Field(None, description='落户地点')

    # 面试相关
    interview_ratio: str | None = Field(None, description='面试比例')
    has_professional_test: str | None = Field(None, description='是否专业测试')

    # 联系方式
    phone1: str | None = Field(None, description='咨询电话1')
    phone2: str | None = Field(None, description='咨询电话2')
    phone3: str | None = Field(None, description='咨询电话3')
    remark: str | None = Field(None, description='备注')


class CreateGangweiParam(GangweiSchemaBase):
    """创建岗位参数"""

    # 统计字段（创建时可选）
    exam_type: str | None = Field(None, description='考试类型')
    apply_count: int | None = Field(None, description='报名人数')
    pass_count: int | None = Field(None, description='审核通过')
    competition_ratio: str | None = Field(None, description='竞争比')
    written_min_score: Decimal | None = Field(None, description='笔试最低分')
    written_avg_score: Decimal | None = Field(None, description='笔试平均分')
    written_max_score: Decimal | None = Field(None, description='笔试最高分')
    interview_min_score: Decimal | None = Field(None, description='面试最低分')
    interview_avg_score: Decimal | None = Field(None, description='面试平均分')
    interview_max_score: Decimal | None = Field(None, description='面试最高分')


class UpdateGangweiParam(SchemaBase):
    """更新岗位参数"""

    # 基础标识
    year: int | None = Field(None, description='年度')
    position_code: str | None = Field(None, description='职位代码')
    serial_no: str | None = Field(None, description='序号')

    # 部门信息
    dept_code: str | None = Field(None, description='部门代码')
    dept_name: str | None = Field(None, description='部门名称')
    bureau: str | None = Field(None, description='用人司局')
    org_nature: str | None = Field(None, description='机构性质')
    org_level: str | None = Field(None, description='机构层级')
    dept_website: str | None = Field(None, description='部门网站')

    # 职位信息
    position_name: str | None = Field(None, description='职位名称')
    position_attr: str | None = Field(None, description='职位属性')
    position_intro: str | None = Field(None, description='职位简介')
    recruit_num: int | None = Field(None, description='招考人数')
    recruit_scope: str | None = Field(None, description='招考范围')
    exam_category: str | None = Field(None, description='考试类别')
    job_rank: str | None = Field(None, description='职级')

    # 报考条件
    major: str | None = Field(None, description='专业')
    education: str | None = Field(None, description='学历')
    degree: str | None = Field(None, description='学位')
    edu_type: str | None = Field(None, description='学历类别')
    politics: str | None = Field(None, description='政治面貌')
    age_requirement: str | None = Field(None, description='年龄要求')
    gender_requirement: str | None = Field(None, description='性别要求')
    ethnicity_requirement: str | None = Field(None, description='民族要求')
    grassroots_years: str | None = Field(None, description='基层工作年限')
    grassroots_project: str | None = Field(None, description='服务基层项目')
    special_position: str | None = Field(None, description='专门职位')
    other_requirement: str | None = Field(None, description='其他条件')

    # 地点信息
    region: str | None = Field(None, description='所属地区')
    work_location: str | None = Field(None, description='工作地点')
    settlement_location: str | None = Field(None, description='落户地点')

    # 面试相关
    interview_ratio: str | None = Field(None, description='面试比例')
    has_professional_test: str | None = Field(None, description='是否专业测试')

    # 联系方式
    phone1: str | None = Field(None, description='咨询电话1')
    phone2: str | None = Field(None, description='咨询电话2')
    phone3: str | None = Field(None, description='咨询电话3')
    remark: str | None = Field(None, description='备注')

    # 统计字段
    exam_type: str | None = Field(None, description='考试类型')
    apply_count: int | None = Field(None, description='报名人数')
    pass_count: int | None = Field(None, description='审核通过')
    competition_ratio: str | None = Field(None, description='竞争比')
    written_min_score: Decimal | None = Field(None, description='笔试最低分')
    written_avg_score: Decimal | None = Field(None, description='笔试平均分')
    written_max_score: Decimal | None = Field(None, description='笔试最高分')
    interview_min_score: Decimal | None = Field(None, description='面试最低分')
    interview_avg_score: Decimal | None = Field(None, description='面试平均分')
    interview_max_score: Decimal | None = Field(None, description='面试最高分')


class GangweiParam(SchemaBase):
    """岗位查询参数"""

    year: int | None = Field(None, description='年度')
    exam_type: str | None = Field(None, description='考试类型')
    region: str | None = Field(None, description='所属地区')
    dept_name: str | None = Field(None, description='部门名称')
    position_name: str | None = Field(None, description='职位名称')
    position_code: str | None = Field(None, description='职位代码')


class DeleteGangweiParam(SchemaBase):
    """删除岗位参数"""

    ids: list[int] = Field(description='岗位 ID 列表')


class GetGangweiDetail(CreateGangweiParam):
    """岗位详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='岗位 ID')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class ImportGangweiResult(SchemaBase):
    """导入岗位结果"""

    total: int = Field(description='总条数')
    success: int = Field(description='成功条数')
    skipped: int = Field(default=0, description='跳过条数（重复）')
    failed: int = Field(description='失败条数')
    errors: list[str] = Field(default_factory=list, description='错误信息列表')


class ParseFileHeaderResult(SchemaBase):
    """解析文件表头结果"""

    file_key: str = Field(description='临时文件标识')
    headers: list[str] = Field(description='文件表头列表')
    preview_data: list[dict] = Field(description='预览数据（前5行）')
    total_rows: int = Field(description='数据总行数')
    db_fields: list[dict] = Field(description='数据库字段定义')
    suggested_mappings: list[dict] = Field(description='智能匹配建议')


class FieldMappingItem(SchemaBase):
    """字段映射项"""

    db_field: str = Field(description='数据库字段名')
    file_column: str | None = Field(None, description='文件列名（单选）')
    file_columns: list[str] | None = Field(None, description='文件列名列表（多选，备注字段用）')
    fixed_value: str | None = Field(None, description='固定值')


class ImportWithMappingParam(SchemaBase):
    """带映射导入参数"""

    file_key: str = Field(description='临时文件标识')
    header_row: int = Field(default=0, description='表头所在行（0 开始）')
    mappings: list[FieldMappingItem] = Field(description='字段映射列表')
    preview: bool = Field(default=False, description='预览模式（不写入数据库）')


class ImportScoreResult(SchemaBase):
    """导入分数结果"""

    total: int = Field(description='总条数（原始行数）')
    positions: int = Field(default=0, description='聚合后岗位数')
    updated: int = Field(description='更新条数')
    not_found: int = Field(description='未找到匹配岗位条数')
    failed: int = Field(description='失败条数')
    errors: list[str] = Field(default_factory=list, description='错误信息列表')
