#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import re
from collections.abc import Sequence
from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.app.gongkao.crud.crud_gangwei import gangwei_dao
from backend.app.gongkao.model.gangwei import GkGangwei
from backend.app.gongkao.schema.gangwei import (
    CreateGangweiParam,
    DeleteGangweiParam,
    GangweiParam,
    ImportGangweiResult,
    ImportScoreResult,
    ImportWithMappingParam,
    UpdateGangweiParam,
)
from backend.common.exception import errors
from backend.core.path_conf import STATIC_DIR

# 临时文件存储目录
TEMP_IMPORT_DIR = STATIC_DIR / 'temp_import'
TEMP_IMPORT_DIR.mkdir(parents=True, exist_ok=True)

# 数据库字段定义（用于前端展示和导入映射）
GANGWEI_FIELDS = [
    # ========== 必填字段（放在最前面）==========
    {'field': 'year', 'label': '年度', 'required': True},
    {
        'field': 'exam_type',
        'label': '考试类型',
        'required': True,
        'options': ['国考', '省考', '事业单位', '选调生', '三支一扶', '军队文职'],
    },
    {'field': 'region', 'label': '所属地区', 'required': True},
    # ========== 基础标识 ==========
    {'field': 'position_code', 'label': '职位代码', 'required': False},
    {'field': 'serial_no', 'label': '序号', 'required': False},
    # ========== 部门信息 ==========
    {'field': 'dept_code', 'label': '部门代码', 'required': False},
    {'field': 'dept_name', 'label': '部门名称', 'required': False},
    {'field': 'bureau', 'label': '用人司局', 'required': False},
    {'field': 'org_nature', 'label': '机构性质', 'required': False},
    {'field': 'org_level', 'label': '机构层级', 'required': False},
    {'field': 'dept_website', 'label': '部门网站', 'required': False},
    # ========== 职位信息 ==========
    {'field': 'position_name', 'label': '职位名称', 'required': False},
    {'field': 'position_attr', 'label': '职位属性', 'required': False},
    {'field': 'position_intro', 'label': '职位简介', 'required': False},
    {'field': 'recruit_num', 'label': '招考人数', 'required': False},
    {'field': 'recruit_scope', 'label': '招考范围', 'required': False},
    {'field': 'exam_category', 'label': '考试类别', 'required': False},
    {'field': 'job_rank', 'label': '职级', 'required': False},
    # ========== 报考条件 ==========
    {'field': 'major', 'label': '专业', 'required': False},
    {'field': 'education', 'label': '学历', 'required': False},
    {'field': 'degree', 'label': '学位', 'required': False},
    {'field': 'edu_type', 'label': '学历类别', 'required': False},
    {'field': 'politics', 'label': '政治面貌', 'required': False},
    {'field': 'age_requirement', 'label': '年龄要求', 'required': False},
    {'field': 'gender_requirement', 'label': '性别要求', 'required': False},
    {'field': 'ethnicity_requirement', 'label': '民族要求', 'required': False},
    {'field': 'grassroots_years', 'label': '基层工作年限', 'required': False},
    {'field': 'grassroots_project', 'label': '服务基层项目', 'required': False},
    {'field': 'special_position', 'label': '专门职位', 'required': False},
    {'field': 'other_requirement', 'label': '其他条件', 'required': False},
    # ========== 地点信息 ==========
    {'field': 'work_location', 'label': '工作地点', 'required': False},
    {'field': 'settlement_location', 'label': '落户地点', 'required': False},
    # ========== 面试相关 ==========
    {'field': 'interview_ratio', 'label': '面试比例', 'required': False},
    {'field': 'has_professional_test', 'label': '是否专业测试', 'required': False},
    # ========== 联系方式 ==========
    {'field': 'phone1', 'label': '咨询电话1', 'required': False},
    {'field': 'phone2', 'label': '咨询电话2', 'required': False},
    {'field': 'phone3', 'label': '咨询电话3', 'required': False},
    {'field': 'remark', 'label': '备注', 'required': False},
    # ========== 统计字段 ==========
    {'field': 'apply_count', 'label': '报名人数', 'required': False},
    {'field': 'pass_count', 'label': '审核通过', 'required': False},
    {'field': 'competition_ratio', 'label': '竞争比', 'required': False},
    {'field': 'written_min_score', 'label': '笔试最低分', 'required': False},
    {'field': 'written_avg_score', 'label': '笔试平均分', 'required': False},
    {'field': 'written_max_score', 'label': '笔试最高分', 'required': False},
    {'field': 'interview_min_score', 'label': '面试最低分', 'required': False},
    {'field': 'interview_avg_score', 'label': '面试平均分', 'required': False},
    {'field': 'interview_max_score', 'label': '面试最高分', 'required': False},
]

# 数值类型字段（用于导入时类型转换）
INT_FIELDS = {'year', 'recruit_num', 'apply_count', 'pass_count'}
DECIMAL_FIELDS = {
    'written_min_score', 'written_avg_score', 'written_max_score',
    'interview_min_score', 'interview_avg_score', 'interview_max_score',
}

# 分数导入专用字段定义
SCORE_FIELDS = [
    # ========== 匹配字段（用于定位岗位）==========
    {'field': 'year', 'label': '年度', 'required': True, 'match_key': True},
    {'field': 'position_code', 'label': '职位代码', 'required': False, 'match_key': True},
    {'field': 'position_name', 'label': '职位名称', 'required': True, 'match_key': True},
    {'field': 'dept_name', 'label': '部门名称', 'required': True, 'match_key': True},
    # ========== 原始分数字段（系统自动按岗位聚合计算 MIN/AVG/MAX）==========
    {'field': 'written_score', 'label': '笔试成绩', 'required': False, 'aggregate': True},
    {'field': 'interview_score', 'label': '面试成绩', 'required': False, 'aggregate': True},
    # ========== 统计字段（直接写入，不聚合）==========
    {'field': 'apply_count', 'label': '报名人数', 'required': False},
    {'field': 'pass_count', 'label': '审核通过', 'required': False},
    {'field': 'competition_ratio', 'label': '竞争比', 'required': False},
]

# 原始分数字段 → 聚合后的数据库字段映射
SCORE_AGGREGATE_MAP = {
    'written_score': {
        'min': 'written_min_score',
        'avg': 'written_avg_score',
        'max': 'written_max_score',
    },
    'interview_score': {
        'min': 'interview_min_score',
        'avg': 'interview_avg_score',
        'max': 'interview_max_score',
    },
}

# 分数导入的数值字段
SCORE_INT_FIELDS = {'year', 'apply_count', 'pass_count'}
SCORE_DECIMAL_FIELDS = {'written_score', 'interview_score'}


def _normalize_str(val: Any) -> str | None:
    """
    规范化字符串：去除首尾空格、压缩中间多余空格、空值统一为 None

    :param val: 原始值
    :return:
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    # 压缩连续空格为单个空格
    return re.sub(r'\s+', ' ', s)


class GangweiService:
    """岗位服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkGangwei:
        """
        获取岗位详情

        :param db: 数据库会话
        :param pk: 岗位 ID
        :return:
        """
        gangwei = await gangwei_dao.get(db, pk)
        if not gangwei:
            raise errors.NotFoundError(msg='岗位不存在')
        return gangwei

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        params: GangweiParam,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[int, Sequence[GkGangwei]]:
        """
        获取岗位列表

        :param db: 数据库会话
        :param params: 查询参数
        :param offset: 偏移量
        :param limit: 限制数量
        :return:
        """
        total = await gangwei_dao.get_count(db, params)
        data = await gangwei_dao.get_list(db, params, offset, limit)
        return total, data

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateGangweiParam, created_by: int) -> GkGangwei:
        """
        创建岗位

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        return await gangwei_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateGangweiParam, updated_by: int) -> int:
        """
        更新岗位

        :param db: 数据库会话
        :param pk: 岗位 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        gangwei = await gangwei_dao.get(db, pk)
        if not gangwei:
            raise errors.NotFoundError(msg='岗位不存在')
        return await gangwei_dao.update(db, pk, obj, updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteGangweiParam) -> int:
        """
        删除岗位

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await gangwei_dao.delete(db, obj.ids)

    @staticmethod
    def _read_file_sync(file_content: bytes, filename: str, header_row: int = 0) -> pd.DataFrame:
        """
        同步读取文件内容

        :param file_content: 文件内容
        :param filename: 文件名
        :param header_row: 表头所在行（0 开始）
        :return:
        """
        file_stream = BytesIO(file_content)
        if filename.endswith('.csv'):
            df = pd.read_csv(file_stream, dtype=str, header=header_row)
        elif filename.endswith('.xlsx'):
            df = pd.read_excel(file_stream, dtype=str, engine='openpyxl', header=header_row)
        elif filename.endswith('.xls'):
            df = pd.read_excel(file_stream, dtype=str, engine='xlrd', header=header_row)
        else:
            raise errors.RequestError(msg='不支持的文件格式，仅支持 CSV、XLS、XLSX')
        return df

    @staticmethod
    def _read_raw_rows_sync(file_content: bytes, filename: str, num_rows: int = 10) -> list[list[str]]:
        """
        读取文件前 N 行原始数据（不指定表头）

        :param file_content: 文件内容
        :param filename: 文件名
        :param num_rows: 读取行数
        :return:
        """
        file_stream = BytesIO(file_content)
        if filename.endswith('.csv'):
            df = pd.read_csv(file_stream, dtype=str, header=None, nrows=num_rows)
        elif filename.endswith('.xlsx'):
            df = pd.read_excel(file_stream, dtype=str, engine='openpyxl', header=None, nrows=num_rows)
        elif filename.endswith('.xls'):
            df = pd.read_excel(file_stream, dtype=str, engine='xlrd', header=None, nrows=num_rows)
        else:
            raise errors.RequestError(msg='不支持的文件格式，仅支持 CSV、XLS、XLSX')
        # 转换为列表，填充空值
        return df.fillna('').values.tolist()

    @staticmethod
    def get_field_definitions() -> list[dict[str, Any]]:
        """获取岗位字段定义"""
        return GANGWEI_FIELDS

    @staticmethod
    async def parse_file_header(*, file: UploadFile, header_row: int = 0) -> dict[str, Any]:
        """
        解析上传文件的表头，返回表头列表和预览数据

        :param file: 上传的文件
        :param header_row: 表头所在行（0 开始，默认第 1 行）
        :return:
        """
        if not file.filename:
            raise errors.RequestError(msg='文件名不能为空')

        # 读取文件内容
        file_content = await file.read()

        # 先读取原始行，供用户选择表头
        raw_rows = await run_in_threadpool(
            GangweiService._read_raw_rows_sync, file_content, file.filename, 10
        )

        # 按指定表头行解析
        df = await run_in_threadpool(
            GangweiService._read_file_sync, file_content, file.filename, header_row
        )

        # 处理列名中的换行符和空格
        df.columns = df.columns.str.replace('\n', '', regex=False).str.strip()

        # 获取表头
        headers = df.columns.tolist()

        # 获取预览数据（前5行）
        preview_df = df.head(5).fillna('')
        preview_data = preview_df.to_dict(orient='records')

        # 保存文件到临时目录
        file_hash = hashlib.md5(file_content).hexdigest()
        file_key = f'{file_hash}_{file.filename}'
        temp_file_path = TEMP_IMPORT_DIR / file_key

        # 保存原始文件
        with open(temp_file_path, 'wb') as f:
            f.write(file_content)

        # 智能匹配建议
        suggested_mappings = GangweiService._suggest_mappings(headers)

        return {
            'file_key': file_key,
            'raw_rows': raw_rows,  # 原始行（供选择表头）
            'header_row': header_row,  # 当前表头行
            'headers': headers,
            'preview_data': preview_data,
            'total_rows': len(df),
            'db_fields': GANGWEI_FIELDS,
            'suggested_mappings': suggested_mappings,
        }

    @staticmethod
    async def reparse_file_header(*, file_key: str, header_row: int) -> dict[str, Any]:
        """
        使用指定表头行重新解析已上传的文件

        :param file_key: 临时文件标识
        :param header_row: 表头所在行（0 开始）
        :return:
        """
        temp_file_path = TEMP_IMPORT_DIR / file_key
        if not temp_file_path.exists():
            raise errors.NotFoundError(msg='临时文件不存在或已过期，请重新上传')

        file_content = temp_file_path.read_bytes()
        filename = file_key.split('_', 1)[1] if '_' in file_key else file_key

        # 读取原始行
        raw_rows = await run_in_threadpool(
            GangweiService._read_raw_rows_sync, file_content, filename, 10
        )

        # 按指定表头行解析
        df = await run_in_threadpool(
            GangweiService._read_file_sync, file_content, filename, header_row
        )

        # 处理列名
        df.columns = df.columns.str.replace('\n', '', regex=False).str.strip()
        headers = df.columns.tolist()

        # 预览数据
        preview_df = df.head(5).fillna('')
        preview_data = preview_df.to_dict(orient='records')

        # 智能匹配
        suggested_mappings = GangweiService._suggest_mappings(headers)

        return {
            'file_key': file_key,
            'raw_rows': raw_rows,
            'header_row': header_row,
            'headers': headers,
            'preview_data': preview_data,
            'total_rows': len(df),
            'db_fields': GANGWEI_FIELDS,
            'suggested_mappings': suggested_mappings,
        }

    @staticmethod
    def _suggest_mappings(headers: list[str]) -> list[dict[str, str]]:
        """
        根据表头智能匹配数据库字段

        :param headers: 文件表头列表
        :return:
        """
        suggestions = []
        label_to_field = {f['label']: f['field'] for f in GANGWEI_FIELDS}

        # 额外的别名映射（用于兼容不同省份的字段名）
        alias_mapping = {
            # ========== 部门相关 ==========
            '部门': 'dept_name',  # 河北省考
            '单位名称': 'dept_name',
            '招录单位': 'dept_name',
            '招录单位全称': 'dept_name',
            '单位代码': 'dept_code',
            '单位': 'org_nature',  # 河北省考（如"机关"）
            '处室名称': 'bureau',
            '用人处室': 'bureau',
            '用人处（科）室': 'bureau',
            '单位类别': 'org_nature',
            '系统类别': 'org_nature',
            '单位级别': 'org_level',
            '部门层级': 'org_level',
            '信息发布网站': 'dept_website',
            # ========== 职位相关 ==========
            '招考职位': 'position_name',
            '招录人数': 'recruit_num',
            '招考计划': 'recruit_num',
            '录用计划数': 'recruit_num',
            '职位描述': 'position_intro',
            '职位工作简介': 'position_intro',
            '试卷类型': 'exam_category',
            '考试试卷对应类别': 'exam_category',
            '申论试卷类型': 'exam_category',
            '使用试题': 'exam_category',
            # ========== 报考条件 ==========
            '专业要求': 'major',
            '所需专业': 'major',
            '学历要求': 'education',
            '学历低限': 'education',
            '学位要求': 'degree',
            '学位低限': 'degree',
            '学历性质要求': 'edu_type',
            '学历性质': 'edu_type',
            '政治面貌要求': 'politics',
            '年龄': 'age_requirement',
            '性别': 'gender_requirement',
            '性别要求': 'gender_requirement',
            '民族': 'ethnicity_requirement',
            '民族要求': 'ethnicity_requirement',
            '基层工作最低年限': 'grassroots_years',
            '基层工作经历': 'grassroots_years',
            '基层工作经历（年）': 'grassroots_years',
            '具有基层工作经历': 'grassroots_years',
            '报考人员身份要求': 'grassroots_years',  # 云南省考：如"两年以上基层工作经历人员"
            '服务基层项目工作经历': 'grassroots_project',
            '是否服务基层项目人员': 'grassroots_project',
            '是否限于面向"服务基层项目"人员报考': 'grassroots_project',
            '其他条件': 'other_requirement',
            '其他招录条件': 'other_requirement',
            '其他要求': 'other_requirement',  # 河北省考
            '其他': 'other_requirement',
            '是否为艰苦边远地区职位': 'special_position',  # 云南省考
            # ========== 地点 ==========
            '市州名称': 'region',
            '单位所属地区': 'region',
            '考区': 'region',
            # ========== 面试 ==========
            '面试人员比例': 'interview_ratio',
            '是否进行专业测试': 'has_professional_test',
            '是否组织专业考试': 'has_professional_test',
            '是否在面试阶段组织专业能力测试': 'has_professional_test',
            # ========== 联系方式 ==========
            '咨询电话': 'phone1',
            '咨询电话号码': 'phone1',
            '有关说明': 'remark',
            # ========== 统计 ==========
            '缴费人数': 'apply_count',
            '报名人数': 'apply_count',
            '进面最低分': 'written_min_score',
            '最低进面分数': 'written_min_score',
            '进面平均分': 'written_avg_score',
            '进面最高分': 'written_max_score',
        }

        for header in headers:
            header_clean = header.strip()
            matched_field = ''

            # 1. 完全匹配标签
            if header_clean in label_to_field:
                matched_field = label_to_field[header_clean]
            # 2. 别名匹配
            elif header_clean in alias_mapping:
                matched_field = alias_mapping[header_clean]
            # 3. 模糊匹配（包含关系）
            else:
                for label, field in label_to_field.items():
                    if label in header_clean or header_clean in label:
                        matched_field = field
                        break

            suggestions.append({
                'file_column': header,
                'db_field': matched_field,
            })

        return suggestions

    @staticmethod
    async def import_with_mapping(
        *,
        db: AsyncSession,
        obj: ImportWithMappingParam,
        created_by: int,
    ) -> ImportGangweiResult:
        """
        使用用户指定的映射关系导入数据

        :param db: 数据库会话
        :param obj: 导入参数
        :param created_by: 创建者 ID
        :return:
        """
        # 读取临时文件
        temp_file_path = TEMP_IMPORT_DIR / obj.file_key
        if not temp_file_path.exists():
            raise errors.NotFoundError(msg='临时文件不存在或已过期，请重新上传')

        file_content = temp_file_path.read_bytes()
        filename = obj.file_key.split('_', 1)[1] if '_' in obj.file_key else obj.file_key
        df = await run_in_threadpool(
            GangweiService._read_file_sync, file_content, filename, obj.header_row
        )

        # 处理列名
        df.columns = df.columns.str.replace('\n', '', regex=False).str.strip()

        # 构建映射字典
        column_mapping: dict[str, str] = {}  # file_column -> db_field（单选）
        multi_column_mapping: dict[str, list[str]] = {}  # db_field -> [file_columns]（多选）
        fixed_values: dict[str, str] = {}  # db_field -> fixed_value
        for m in obj.mappings:
            if m.file_columns:
                # 多选映射（备注字段）
                multi_column_mapping[m.db_field] = m.file_columns
            elif m.file_column:
                column_mapping[m.file_column] = m.db_field
            elif m.fixed_value is not None:
                fixed_values[m.db_field] = m.fixed_value

        total = len(df)
        success = 0
        failed = 0
        error_list: list[str] = []
        create_params: list[CreateGangweiParam] = []

        # 必填字段检查
        required_fields = {'year'}
        mapped_fields = set(column_mapping.values()) | set(multi_column_mapping.keys()) | set(fixed_values.keys())
        missing_required = required_fields - mapped_fields
        if missing_required:
            field_labels = [f['label'] for f in GANGWEI_FIELDS if f['field'] in missing_required]
            raise errors.RequestError(msg=f'缺少必填字段映射: {", ".join(field_labels)}')

        for idx, row in df.iterrows():
            row_num = idx + 2
            row_dict = row.where(pd.notna(row), None).to_dict()

            # 根据映射关系转换数据
            mapped_row: dict[str, Any] = {}
            # 先应用固定值
            mapped_row.update(fixed_values)
            # 应用单选列映射
            for file_col, db_field in column_mapping.items():
                if file_col in row_dict:
                    val = row_dict[file_col]
                    # 将值转换为字符串（数值字段后续会再处理）
                    if val is not None:
                        val_str = str(val).strip()
                        if val_str and val_str.lower() != 'nan':
                            mapped_row[db_field] = val_str
            # 应用多选列映射（合并为 "列名: 值; 列名: 值" 格式）
            for db_field, file_cols in multi_column_mapping.items():
                parts = []
                for col in file_cols:
                    val = row_dict.get(col)
                    if val is not None:
                        # 确保转换为字符串，并过滤空值和 nan
                        val_str = str(val).strip()
                        if val_str and val_str.lower() != 'nan':
                            parts.append(f'{col}: {val_str}')
                if parts:
                    mapped_row[db_field] = '; '.join(parts)

            # 处理数值类型字段
            for field in INT_FIELDS:
                if mapped_row.get(field) is not None:
                    try:
                        mapped_row[field] = int(float(mapped_row[field]))
                    except (ValueError, TypeError):
                        mapped_row[field] = None

            for field in DECIMAL_FIELDS:
                if mapped_row.get(field) is not None:
                    try:
                        mapped_row[field] = float(mapped_row[field])
                    except (ValueError, TypeError):
                        mapped_row[field] = None

            try:
                create_param = CreateGangweiParam(**mapped_row)
                create_params.append(create_param)
            except ValidationError as e:
                failed += 1
                error_msg = '; '.join([f"{err['loc']}: {err['msg']}" for err in e.errors()])
                error_list.append(f'第 {row_num} 行: {error_msg}')

        # 事务性导入：只有全部验证通过才写入
        if error_list:
            return ImportGangweiResult(
                total=total,
                success=0,
                skipped=0,
                failed=failed,
                errors=error_list[:50],
            )

        # 去重检查：按年度+职位代码+职位名称+部门名称
        skipped = 0
        if create_params:
            # 按年度分组检查
            year_groups: dict[int, list[CreateGangweiParam]] = {}
            for param in create_params:
                year_groups.setdefault(param.year, []).append(param)

            filtered_params: list[CreateGangweiParam] = []
            for year, params in year_groups.items():
                # 获取待检查的 key 列表
                keys = [(p.position_code, p.position_name, p.dept_name) for p in params]
                # 查询已存在的记录
                existing_keys = await gangwei_dao.get_existing_keys(db, year, keys)

                for param in params:
                    key = (param.position_code, param.position_name, param.dept_name)
                    if key in existing_keys:
                        skipped += 1
                    else:
                        filtered_params.append(param)

            create_params = filtered_params

        # 全部验证通过，批量创建
        if create_params:
            await gangwei_dao.bulk_create(db, create_params, created_by)
            success = len(create_params)

        # 清理临时文件
        try:
            temp_file_path.unlink()
        except Exception:
            pass

        return ImportGangweiResult(
            total=total,
            success=success,
            skipped=skipped,
            failed=failed,
            errors=error_list[:50],
        )

    @staticmethod
    def get_score_field_definitions() -> list[dict[str, Any]]:
        """获取分数导入字段定义"""
        return SCORE_FIELDS

    @staticmethod
    async def parse_score_file_header(*, file: UploadFile, header_row: int = 0) -> dict[str, Any]:
        """
        解析分数导入文件的表头

        :param file: 上传的文件
        :param header_row: 表头所在行（0 开始）
        :return:
        """
        if not file.filename:
            raise errors.RequestError(msg='文件名不能为空')

        file_content = await file.read()

        # 读取原始行
        raw_rows = await run_in_threadpool(
            GangweiService._read_raw_rows_sync, file_content, file.filename, 10
        )

        # 按指定表头行解析
        df = await run_in_threadpool(
            GangweiService._read_file_sync, file_content, file.filename, header_row
        )

        df.columns = df.columns.str.replace('\n', '', regex=False).str.strip()
        headers = df.columns.tolist()

        # 预览数据
        preview_df = df.head(5).fillna('')
        preview_data = preview_df.to_dict(orient='records')

        # 保存文件
        file_hash = hashlib.md5(file_content).hexdigest()
        file_key = f'score_{file_hash}_{file.filename}'
        temp_file_path = TEMP_IMPORT_DIR / file_key

        with open(temp_file_path, 'wb') as f:
            f.write(file_content)

        # 智能匹配（针对分数字段）
        suggested_mappings = GangweiService._suggest_score_mappings(headers)

        return {
            'file_key': file_key,
            'raw_rows': raw_rows,
            'header_row': header_row,
            'headers': headers,
            'preview_data': preview_data,
            'total_rows': len(df),
            'db_fields': SCORE_FIELDS,
            'suggested_mappings': suggested_mappings,
        }

    @staticmethod
    async def reparse_score_file_header(*, file_key: str, header_row: int) -> dict[str, Any]:
        """
        使用指定表头行重新解析分数导入文件

        :param file_key: 临时文件标识
        :param header_row: 表头所在行
        :return:
        """
        temp_file_path = TEMP_IMPORT_DIR / file_key
        if not temp_file_path.exists():
            raise errors.NotFoundError(msg='临时文件不存在或已过期，请重新上传')

        file_content = temp_file_path.read_bytes()
        filename = file_key.split('_', 2)[2] if file_key.count('_') >= 2 else file_key

        raw_rows = await run_in_threadpool(
            GangweiService._read_raw_rows_sync, file_content, filename, 10
        )

        df = await run_in_threadpool(
            GangweiService._read_file_sync, file_content, filename, header_row
        )

        df.columns = df.columns.str.replace('\n', '', regex=False).str.strip()
        headers = df.columns.tolist()

        preview_df = df.head(5).fillna('')
        preview_data = preview_df.to_dict(orient='records')

        suggested_mappings = GangweiService._suggest_score_mappings(headers)

        return {
            'file_key': file_key,
            'raw_rows': raw_rows,
            'header_row': header_row,
            'headers': headers,
            'preview_data': preview_data,
            'total_rows': len(df),
            'db_fields': SCORE_FIELDS,
            'suggested_mappings': suggested_mappings,
        }

    @staticmethod
    def _suggest_score_mappings(headers: list[str]) -> list[dict[str, str]]:
        """
        分数导入的智能匹配建议

        :param headers: 文件表头
        :return:
        """
        suggestions = []
        label_to_field = {f['label']: f['field'] for f in SCORE_FIELDS}

        # 分数导入的别名映射（映射到原始分数字段，系统自动聚合）
        alias_mapping = {
            '单位名称': 'dept_name',
            '招录单位': 'dept_name',
            '招录单位全称': 'dept_name',
            '报考单位': 'dept_name',
            '招考职位': 'position_name',
            '报考职位': 'position_name',
            '缴费人数': 'apply_count',
            '报名人数': 'apply_count',
            # 笔试成绩相关（映射到 written_score，系统自动计算 MIN/AVG/MAX）
            '笔试成绩': 'written_score',
            '笔试分数': 'written_score',
            '笔试总分': 'written_score',
            '公共科目笔试成绩': 'written_score',
            '进面分数': 'written_score',
            # 面试成绩相关（映射到 interview_score，系统自动计算 MIN/AVG/MAX）
            '面试成绩': 'interview_score',
            '面试分数': 'interview_score',
            '面试得分': 'interview_score',
        }

        for header in headers:
            header_clean = header.strip()
            matched_field = ''

            if header_clean in label_to_field:
                matched_field = label_to_field[header_clean]
            elif header_clean in alias_mapping:
                matched_field = alias_mapping[header_clean]
            else:
                for label, field in label_to_field.items():
                    if label in header_clean or header_clean in label:
                        matched_field = field
                        break

            suggestions.append({
                'file_column': header,
                'db_field': matched_field,
            })

        return suggestions

    @staticmethod
    async def import_scores_with_mapping(
        *,
        db: AsyncSession,
        obj: ImportWithMappingParam,
        updated_by: int,
    ) -> ImportScoreResult:
        """
        使用用户指定的映射关系导入分数数据（支持按岗位聚合）

        数据文件是每人一行，系统会自动按岗位分组，计算分数的 MIN/AVG/MAX

        :param db: 数据库会话
        :param obj: 导入参数
        :param updated_by: 修改者 ID
        :return:
        """
        from decimal import Decimal, ROUND_HALF_UP

        temp_file_path = TEMP_IMPORT_DIR / obj.file_key
        if not temp_file_path.exists():
            raise errors.NotFoundError(msg='临时文件不存在或已过期，请重新上传')

        file_content = temp_file_path.read_bytes()
        filename = obj.file_key.split('_', 2)[2] if obj.file_key.count('_') >= 2 else obj.file_key
        df = await run_in_threadpool(
            GangweiService._read_file_sync, file_content, filename, obj.header_row
        )

        df.columns = df.columns.str.replace('\n', '', regex=False).str.strip()

        # 构建映射字典
        column_mapping: dict[str, str] = {}
        fixed_values: dict[str, str] = {}
        for m in obj.mappings:
            if m.file_column:
                column_mapping[m.file_column] = m.db_field
            elif m.fixed_value is not None:
                fixed_values[m.db_field] = m.fixed_value

        total = len(df)
        error_list: list[str] = []

        # 检查必填匹配字段
        required_match_fields = {'year', 'position_name', 'dept_name'}
        match_fields = {'year', 'position_code', 'position_name', 'dept_name'}
        mapped_fields = set(column_mapping.values()) | set(fixed_values.keys())
        missing_match = required_match_fields - mapped_fields
        if missing_match:
            field_labels = [f['label'] for f in SCORE_FIELDS if f['field'] in missing_match]
            raise errors.RequestError(msg=f'缺少匹配字段映射: {", ".join(field_labels)}')

        # 获取需要聚合的字段
        aggregate_fields = {f['field'] for f in SCORE_FIELDS if f.get('aggregate')}

        # 第一步：解析所有行，按岗位分组
        # key: (year, position_code, position_name, dept_name) -> list of row data
        position_groups: dict[tuple, list[dict[str, Any]]] = {}
        parse_failed = 0

        for idx, row in df.iterrows():
            row_num = idx + 2
            row_dict = row.where(pd.notna(row), None).to_dict()

            # 转换映射数据
            mapped_row: dict[str, Any] = {}
            mapped_row.update(fixed_values)
            mapped_row['_row_num'] = row_num  # 记录原始行号

            for file_col, db_field in column_mapping.items():
                if file_col in row_dict:
                    val = row_dict[file_col]
                    if val is not None:
                        val_str = str(val).strip()
                        if val_str and val_str.lower() != 'nan':
                            mapped_row[db_field] = val_str

            # 转换数值类型
            for field in SCORE_INT_FIELDS:
                if mapped_row.get(field) is not None:
                    try:
                        mapped_row[field] = int(float(mapped_row[field]))
                    except (ValueError, TypeError):
                        mapped_row[field] = None

            for field in SCORE_DECIMAL_FIELDS:
                if mapped_row.get(field) is not None:
                    try:
                        mapped_row[field] = float(mapped_row[field])
                    except (ValueError, TypeError):
                        mapped_row[field] = None

            # 提取匹配字段组成 key（规范化处理，避免空值/空格差异导致分组错误）
            year = mapped_row.get('year')
            position_code = _normalize_str(mapped_row.get('position_code'))
            position_name = _normalize_str(mapped_row.get('position_name'))
            dept_name = _normalize_str(mapped_row.get('dept_name'))

            if not year:
                parse_failed += 1
                error_list.append(f'第 {row_num} 行: 年度不能为空')
                continue

            # 添加到分组
            key = (year, position_code, position_name, dept_name)
            if key not in position_groups:
                position_groups[key] = []
            position_groups[key].append(mapped_row)

        # 第二步：对每个岗位分组进行聚合计算
        updated = 0
        not_found = 0
        failed = 0

        for key, rows in position_groups.items():
            year, position_code, position_name, dept_name = key
            row_nums = [r['_row_num'] for r in rows]
            row_nums_str = f'{row_nums[0]}-{row_nums[-1]}' if len(rows) > 1 else str(row_nums[0])

            # 查找匹配的岗位
            gangwei, match_count = await gangwei_dao.find_by_match_key(
                db, year, position_code, position_name, dept_name
            )

            if not gangwei:
                not_found += 1
                error_list.append(
                    f'行 {row_nums_str}: 未找到匹配岗位 '
                    f'(年度={year}, 职位代码={position_code}, 职位名称={position_name}, 部门={dept_name}), '
                    f'共 {len(rows)} 人'
                )
                continue

            if match_count > 1:
                error_list.append(
                    f'行 {row_nums_str}: 匹配到 {match_count} 条岗位，已更新第一条 '
                    f'(年度={year}, 职位名称={position_name}, 部门={dept_name})'
                )

            # 聚合计算
            score_data: dict[str, Any] = {}

            # 处理聚合字段（written_score, interview_score）
            for agg_field in aggregate_fields:
                # 收集该字段的所有有效值
                values = [r[agg_field] for r in rows if r.get(agg_field) is not None]
                if values:
                    # 计算 MIN/AVG/MAX
                    min_val = min(values)
                    max_val = max(values)
                    avg_val = sum(values) / len(values)
                    # 保留两位小数
                    avg_val = float(Decimal(str(avg_val)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

                    # 映射到数据库字段
                    if agg_field in SCORE_AGGREGATE_MAP:
                        field_map = SCORE_AGGREGATE_MAP[agg_field]
                        score_data[field_map['min']] = min_val
                        score_data[field_map['avg']] = avg_val
                        score_data[field_map['max']] = max_val

            # 处理非聚合字段（取第一行的值）
            first_row = rows[0]
            for field in first_row:
                if field.startswith('_'):
                    continue
                if field in match_fields:
                    continue
                if field in aggregate_fields:
                    continue
                val = first_row.get(field)
                if val is not None:
                    score_data[field] = val

            if score_data:
                if obj.preview:
                    updated += 1
                else:
                    try:
                        await gangwei_dao.update_scores(db, gangwei.id, score_data, updated_by)
                        updated += 1
                    except Exception as e:
                        failed += 1
                        error_list.append(f'行 {row_nums_str}: 更新失败 - {str(e)}')
            else:
                updated += 1

        # 预览模式不清理临时文件
        if not obj.preview:
            try:
                temp_file_path.unlink()
            except Exception:
                pass

        return ImportScoreResult(
            total=total,
            positions=len(position_groups),
            updated=updated,
            not_found=not_found,
            failed=failed + parse_failed,
            errors=error_list[:50],
        )


gangwei_service: GangweiService = GangweiService()
