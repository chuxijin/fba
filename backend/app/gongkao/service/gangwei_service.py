#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from io import BytesIO

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
    ImportGangweiItem,
    ImportGangweiResult,
    UpdateGangweiParam,
)
from backend.common.exception import errors


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
        # 检查联合唯一键是否已存在
        existing = await gangwei_dao.get_by_unique_key(
            db,
            year=obj.year,
            org_region=obj.org_region,
            position_code=obj.position_code,
        )
        if existing:
            raise errors.ForbiddenError(msg='该年度、地区、职位代码的岗位已存在')
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

        # 如果更新了联合唯一键字段，需要检查是否冲突
        new_year = obj.year if obj.year is not None else gangwei.year
        new_region = obj.org_region if obj.org_region is not None else gangwei.org_region
        new_code = obj.position_code if obj.position_code is not None else gangwei.position_code

        if (new_year, new_region, new_code) != (gangwei.year, gangwei.org_region, gangwei.position_code):
            existing = await gangwei_dao.get_by_unique_key(db, new_year, new_region, new_code)
            if existing and existing.id != pk:
                raise errors.ForbiddenError(msg='该年度、地区、职位代码的岗位已存在')

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
    def _read_file_sync(file_content: bytes, filename: str) -> pd.DataFrame:
        """
        同步读取文件内容

        :param file_content: 文件内容
        :param filename: 文件名
        :return:
        """
        file_stream = BytesIO(file_content)
        if filename.endswith('.csv'):
            df = pd.read_csv(file_stream, dtype=str)
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_stream, dtype=str)
        else:
            raise errors.RequestError(msg='不支持的文件格式，仅支持 CSV、XLS、XLSX')
        return df

    @staticmethod
    async def import_from_file(
        *,
        db: AsyncSession,
        file: UploadFile,
        created_by: int,
    ) -> ImportGangweiResult:
        """
        从文件导入岗位数据

        :param db: 数据库会话
        :param file: 上传的文件
        :param created_by: 创建者 ID
        :return:
        """
        if not file.filename:
            raise errors.RequestError(msg='文件名不能为空')

        # 读取文件内容
        file_content = await file.read()
        df = await run_in_threadpool(GangweiService._read_file_sync, file_content, file.filename)

        # 处理列名中的换行符和空格
        df.columns = df.columns.str.replace('\n', '', regex=False).str.strip()

        # 字段映射
        column_mapping = {
            '笔试最低分': '笔试最低分',
            '笔试平均分': '笔试平均分',
            '笔试最高分': '笔试最高分',
            '面试最低分': '面试最低分',
            '面试平均分': '面试平均分',
            '面试最高分': '面试最高分',
        }
        df = df.rename(columns=column_mapping)

        total = len(df)
        success = 0
        failed = 0
        error_list: list[str] = []
        create_params: list[CreateGangweiParam] = []

        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel 行号从 2 开始（第 1 行是表头）
            row_dict = row.where(pd.notna(row), None).to_dict()

            # 处理数值类型字段
            for field in ['年度', '招收人数', '报名数', '审核通过']:
                if row_dict.get(field) is not None:
                    try:
                        row_dict[field] = int(float(row_dict[field]))
                    except (ValueError, TypeError):
                        row_dict[field] = None

            for field in ['笔试最低分', '笔试平均分', '笔试最高分', '面试最低分', '面试平均分', '面试最高分']:
                if row_dict.get(field) is not None:
                    try:
                        row_dict[field] = float(row_dict[field])
                    except (ValueError, TypeError):
                        row_dict[field] = None

            try:
                item = ImportGangweiItem.model_validate(row_dict)
                create_param = CreateGangweiParam(**item.model_dump(by_alias=False))

                # 检查是否已存在
                existing = await gangwei_dao.get_by_unique_key(
                    db,
                    year=create_param.year,
                    org_region=create_param.org_region,
                    position_code=create_param.position_code,
                )
                if existing:
                    failed += 1
                    error_list.append(f'第 {row_num} 行: 该年度、地区、职位代码的岗位已存在')
                    continue

                create_params.append(create_param)

            except ValidationError as e:
                failed += 1
                error_msg = '; '.join([f"{err['loc']}: {err['msg']}" for err in e.errors()])
                error_list.append(f'第 {row_num} 行: {error_msg}')

        # 批量创建
        if create_params:
            await gangwei_dao.bulk_create(db, create_params, created_by)
            success = len(create_params)

        return ImportGangweiResult(
            total=total,
            success=success,
            failed=failed,
            errors=error_list[:50],  # 最多返回 50 条错误信息
        )


gangwei_service: GangweiService = GangweiService()
