#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.job.model.job import JobPosting
from backend.app.job.schema.job import CreateJobPostingParam, UpdateJobPostingParam


class CRUDJobPosting(CRUDPlus[JobPosting]):
    """岗位数据库操作类"""

    async def get_list(self, params: dict[str, Any]) -> Select:
        """
        获取岗位列表查询语句

        :param params: 过滤参数字典
        :return:
        """
        filters: dict[str, Any] = {}

        # 基础等值/范围过滤
        class_val = params.get('class')
        if class_val:
            filters['class'] = class_val

        publish_date_start = params.get('publish_date_start')
        publish_date_end = params.get('publish_date_end')
        expire_date_start = params.get('expire_date_start')
        expire_date_end = params.get('expire_date_end')

        if publish_date_start:
            filters['publish_date__gte'] = publish_date_start
        if publish_date_end:
            filters['publish_date__lte'] = publish_date_end
        if expire_date_start:
            filters['expire_date__gte'] = expire_date_start
        if expire_date_end:
            filters['expire_date__lte'] = expire_date_end

        # JSON 列包含/交集匹配（根据 sqlalchemy-crud-plus 的约定）
        job_title_ids = params.get('job_title_ids') or []
        address_ids = params.get('address_ids') or []
        degree_ids = params.get('degree_ids') or []
        english_ids = params.get('english_ids') or []
        major_ids = params.get('major_ids') or []
        tags = params.get('tags') or []
        industry = params.get('industry') or []
        org_type = params.get('org_type') or []

        if job_title_ids:
            filters['job_title_id__overlap'] = job_title_ids
        if address_ids:
            filters['address_id__overlap'] = address_ids
        if major_ids:
            filters['major_id__overlap'] = major_ids
        if tags:
            filters['tags__overlap'] = tags
        if industry:
            filters['industry__overlap'] = industry
        if org_type:
            filters['org_type__overlap'] = org_type

        # 学位与英语等可以在 position_require_new JSON 内另行处理（此处先保留外部 degree_ids/english_ids 给 service）

        return await self.select_order('publish_date', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: dict[str, Any]) -> None:
        """
        创建岗位

        :param db: 数据库会话
        :param obj: 创建参数字典
        :return:
        """
        await self.create_model(db, obj)

    async def create_by_schema(self, db: AsyncSession, obj: CreateJobPostingParam) -> None:
        """
        创建岗位（Schema 入参）

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: dict[str, Any] | UpdateJobPostingParam) -> int:
        """
        更新岗位

        :param db: 数据库会话
        :param pk: 岗位 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, ids: list[int]) -> int:
        """
        批量删除岗位

        :param db: 数据库会话
        :param ids: 岗位 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=ids)


