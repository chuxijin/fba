#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ==================== 教育经历 ====================


class UserEducationSchemaBase(SchemaBase):
    """教育经历基础"""

    edu_level: str = Field(description='学历层次: 专科/本科/硕士研究生/博士研究生')
    degree: str | None = Field(None, description='学位: 学士/硕士/博士')
    edu_type: str = Field(default='全日制', description='学历性质: 全日制/非全日制')
    major_code: str | None = Field(None, description='专业代码')
    major_name: str | None = Field(None, description='专业名称')
    major_category: str | None = Field(None, description='专业类')
    major_discipline: str | None = Field(None, description='学科门类')
    school_name: str | None = Field(None, description='毕业院校')
    school_type: str | None = Field(None, description='院校类型: 985/211/双一流/普通本科/专科')
    enrollment_batch: str | None = Field(None, description='招生批次: 本科一批/本科二批/专科批')
    start_date: date | None = Field(None, description='入学时间')
    end_date: date | None = Field(None, description='毕业时间')
    is_highest: bool = Field(default=False, description='是否最高学历')


class CreateUserEducationParam(UserEducationSchemaBase):
    """创建教育经历参数"""

    pass


class UpdateUserEducationParam(SchemaBase):
    """更新教育经历参数"""

    edu_level: str | None = Field(None, description='学历层次')
    degree: str | None = Field(None, description='学位')
    edu_type: str | None = Field(None, description='学历性质')
    major_code: str | None = Field(None, description='专业代码')
    major_name: str | None = Field(None, description='专业名称')
    major_category: str | None = Field(None, description='专业类')
    major_discipline: str | None = Field(None, description='学科门类')
    school_name: str | None = Field(None, description='毕业院校')
    school_type: str | None = Field(None, description='院校类型')
    enrollment_batch: str | None = Field(None, description='招生批次')
    start_date: date | None = Field(None, description='入学时间')
    end_date: date | None = Field(None, description='毕业时间')
    is_highest: bool | None = Field(None, description='是否最高学历')


class GetUserEducationDetail(UserEducationSchemaBase):
    """教育经历详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')


# ==================== 地区偏好 ====================


class UserRegionPreferenceSchemaBase(SchemaBase):
    """地区偏好基础"""

    province_code: str | None = Field(None, description='省代码')
    city_code: str | None = Field(None, description='市代码')
    county_code: str | None = Field(None, description='县/区代码')
    priority: int = Field(default=1, description='优先级: 1最高')
    include_sub_regions: bool = Field(default=True, description='是否包含下级区域')
    accept_remote_area: bool = Field(default=False, description='是否接受艰苦边远')


class CreateUserRegionPreferenceParam(UserRegionPreferenceSchemaBase):
    """创建地区偏好参数"""

    pass


class UpdateUserRegionPreferenceParam(SchemaBase):
    """更新地区偏好参数"""

    province_code: str | None = Field(None, description='省代码')
    city_code: str | None = Field(None, description='市代码')
    county_code: str | None = Field(None, description='县/区代码')
    priority: int | None = Field(None, description='优先级')
    include_sub_regions: bool | None = Field(None, description='是否包含下级区域')
    accept_remote_area: bool | None = Field(None, description='是否接受艰苦边远')


class GetUserRegionPreferenceDetail(UserRegionPreferenceSchemaBase):
    """地区偏好详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')


# ==================== 资格证书 ====================


class UserCertificateSchemaBase(SchemaBase):
    """资格证书基础"""

    cert_type: str = Field(description='证书类型: 职业资格/专业技术/语言能力')
    cert_name: str = Field(description='证书名称')
    cert_level: str | None = Field(None, description='证书等级')
    cert_no: str | None = Field(None, description='证书编号')
    issue_date: date | None = Field(None, description='取得时间')
    expire_date: date | None = Field(None, description='有效期至')


class CreateUserCertificateParam(UserCertificateSchemaBase):
    """创建资格证书参数"""

    pass


class UpdateUserCertificateParam(SchemaBase):
    """更新资格证书参数"""

    cert_type: str | None = Field(None, description='证书类型')
    cert_name: str | None = Field(None, description='证书名称')
    cert_level: str | None = Field(None, description='证书等级')
    cert_no: str | None = Field(None, description='证书编号')
    issue_date: date | None = Field(None, description='取得时间')
    expire_date: date | None = Field(None, description='有效期至')


class GetUserCertificateDetail(UserCertificateSchemaBase):
    """资格证书详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')


# ==================== 工作经历 ====================


class UserWorkExperienceSchemaBase(SchemaBase):
    """工作经历基础"""

    company_name: str = Field(description='单位名称')
    company_type: str | None = Field(None, description='单位性质: 党政机关/事业单位/国企/民企/外企')
    position: str | None = Field(None, description='岗位名称')
    department: str | None = Field(None, description='部门')
    start_date: date | None = Field(None, description='开始时间')
    end_date: date | None = Field(None, description='结束时间')
    is_current: bool = Field(default=False, description='是否当前工作')
    is_grassroots: bool = Field(default=False, description='是否基层工作经历')
    grassroots_project: str | None = Field(None, description='服务基层项目: 三支一扶/西部计划/特岗教师/大学生村官')
    service_region_code: str | None = Field(None, description='服务地区代码')
    description: str | None = Field(None, description='工作描述')


class CreateUserWorkExperienceParam(UserWorkExperienceSchemaBase):
    """创建工作经历参数"""

    pass


class UpdateUserWorkExperienceParam(SchemaBase):
    """更新工作经历参数"""

    company_name: str | None = Field(None, description='单位名称')
    company_type: str | None = Field(None, description='单位性质')
    position: str | None = Field(None, description='岗位名称')
    department: str | None = Field(None, description='部门')
    start_date: date | None = Field(None, description='开始时间')
    end_date: date | None = Field(None, description='结束时间')
    is_current: bool | None = Field(None, description='是否当前工作')
    is_grassroots: bool | None = Field(None, description='是否基层工作经历')
    grassroots_project: str | None = Field(None, description='服务基层项目')
    service_region_code: str | None = Field(None, description='服务地区代码')
    description: str | None = Field(None, description='工作描述')


class GetUserWorkExperienceDetail(UserWorkExperienceSchemaBase):
    """工作经历详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')


# ==================== 荣誉成就 ====================


class UserHonorSchemaBase(SchemaBase):
    """荣誉成就基础"""

    honor_type: str = Field(description='荣誉类型: 党员荣誉/学术荣誉/技能竞赛/社会实践')
    honor_name: str = Field(description='荣誉名称')
    honor_level: str | None = Field(None, description='荣誉级别: 国家级/省级/市级/校级')
    issue_org: str | None = Field(None, description='颁发机构')
    issue_date: date | None = Field(None, description='取得时间')
    description: str | None = Field(None, description='荣誉说明')


class CreateUserHonorParam(UserHonorSchemaBase):
    """创建荣誉成就参数"""

    pass


class UpdateUserHonorParam(SchemaBase):
    """更新荣誉成就参数"""

    honor_type: str | None = Field(None, description='荣誉类型')
    honor_name: str | None = Field(None, description='荣誉名称')
    honor_level: str | None = Field(None, description='荣誉级别')
    issue_org: str | None = Field(None, description='颁发机构')
    issue_date: date | None = Field(None, description='取得时间')
    description: str | None = Field(None, description='荣誉说明')


class GetUserHonorDetail(UserHonorSchemaBase):
    """荣誉成就详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')


# ==================== 用户画像主表 ====================


class UserProfileSchemaBase(SchemaBase):
    """用户画像基础"""

    birth_date: date | None = Field(None, description='出生日期')
    gender: str | None = Field(None, description='性别')
    ethnicity: str | None = Field(None, description='民族')
    hukou_region_code: str | None = Field(None, description='户籍地区代码')
    origin_region_code: str | None = Field(None, description='生源地代码')
    politics: str | None = Field(None, description='政治面貌')
    special_identity: str | None = Field(None, description='特殊身份: 退役军人/残疾人/烈士子女等')
    is_fresh_graduate: bool = Field(default=False, description='是否为择业期应届生')
    total_work_years: int = Field(default=0, description='总工作年限（月）')


class CreateUserProfileParam(UserProfileSchemaBase):
    """创建用户画像参数"""

    educations: list[CreateUserEducationParam] = Field(default_factory=list, description='教育经历')
    region_preferences: list[CreateUserRegionPreferenceParam] = Field(default_factory=list, description='地区偏好')
    certificates: list[CreateUserCertificateParam] = Field(default_factory=list, description='资格证书')
    work_experiences: list[CreateUserWorkExperienceParam] = Field(default_factory=list, description='工作经历')
    honors: list[CreateUserHonorParam] = Field(default_factory=list, description='荣誉成就')


class UpdateUserProfileParam(SchemaBase):
    """更新用户画像参数"""

    birth_date: date | None = Field(None, description='出生日期')
    gender: str | None = Field(None, description='性别')
    ethnicity: str | None = Field(None, description='民族')
    hukou_region_code: str | None = Field(None, description='户籍地区代码')
    origin_region_code: str | None = Field(None, description='生源地代码')
    politics: str | None = Field(None, description='政治面貌')
    special_identity: str | None = Field(None, description='特殊身份')
    is_fresh_graduate: bool | None = Field(None, description='是否为择业期应届生')
    total_work_years: int | None = Field(None, description='总工作年限（月）')

    # 子表整体更新
    educations: list[CreateUserEducationParam] | None = Field(None, description='教育经历')
    region_preferences: list[CreateUserRegionPreferenceParam] | None = Field(None, description='地区偏好')
    certificates: list[CreateUserCertificateParam] | None = Field(None, description='资格证书')
    work_experiences: list[CreateUserWorkExperienceParam] | None = Field(None, description='工作经历')
    honors: list[CreateUserHonorParam] | None = Field(None, description='荣誉成就')


class UpdateUserProfileMainParam(SchemaBase):
    """更新用户画像主表参数（不包含子表）"""

    birth_date: date | None = Field(None, description='出生日期')
    gender: str | None = Field(None, description='性别')
    ethnicity: str | None = Field(None, description='民族')
    hukou_region_code: str | None = Field(None, description='户籍地区代码')
    origin_region_code: str | None = Field(None, description='生源地代码')
    politics: str | None = Field(None, description='政治面貌')
    special_identity: str | None = Field(None, description='特殊身份')
    is_fresh_graduate: bool | None = Field(None, description='是否为择业期应届生')
    total_work_years: int | None = Field(None, description='总工作年限（月）')


class GetUserProfileDetail(UserProfileSchemaBase):
    """用户画像详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    user_id: int = Field(description='关联用户ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')

    # 子表数据
    educations: list[GetUserEducationDetail] = Field(default_factory=list, description='教育经历')
    region_preferences: list[GetUserRegionPreferenceDetail] = Field(default_factory=list, description='地区偏好')
    certificates: list[GetUserCertificateDetail] = Field(default_factory=list, description='资格证书')
    work_experiences: list[GetUserWorkExperienceDetail] = Field(default_factory=list, description='工作经历')
    honors: list[GetUserHonorDetail] = Field(default_factory=list, description='荣誉成就')
