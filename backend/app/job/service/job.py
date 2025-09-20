#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any
import json

from sqlalchemy import Select, and_, cast
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.job.crud.job import CRUDJobPosting
from backend.app.job.model.job import JobPosting
from backend.app.job.schema.job import (
    CreateJobPostingParam,
    DeleteJobPostingParam,
    JobPostingDetail,
    JobSearchParam,
    UpdateJobPostingParam,
)
from backend.common.exception import errors
from backend.common.pagination import PageData, DependsPagination
from backend.common.response.response_schema import ResponseSchemaModel
from backend.database.db import async_db_session
from backend.database.redis import redis_client
from fastapi_pagination.ext.sqlalchemy import apaginate


job_posting_dao = CRUDJobPosting(JobPosting)


class JobService:
    """岗位服务类"""

    @staticmethod
    async def get_select(params: JobSearchParam) -> Select:
        """
        构建岗位列表查询语句

        :param params: 检索参数
        :return:
        """
        # 先由 CRUD 生成基础过滤
        base_select = await job_posting_dao.get_list(
            {
                'class': params.class_,
                'job_title_ids': params.job_title_ids,
                'address_ids': params.address_ids,
                'degree_ids': params.degree_ids,
                'english_ids': params.english_ids,
                'industry': params.industry,
                'major_ids': params.major_ids,
                'org_type': params.org_type,
                'other_ids': params.other_ids,
                'personal_ids': params.personal_ids,
                'school_ids': params.school_ids,
                'tags': params.tags,
                'publish_date_start': params.publish_date_start,
                'publish_date_end': params.publish_date_end,
                'expire_date_start': params.expire_date_start,
                'expire_date_end': params.expire_date_end,
            }
        )

        # 对 position_require_new JSON 进行额外过滤（学位/英语等），尽量保持与简化方案一致
        conditions = []
        if params.degree_ids:
            # 示例：degree_ids 为内部约定的枚举映射，这里仅示例性演示 overlap 检查
            # 如果你有具体的 degree 映射关系，可在此展开具体键位匹配
            pass
        if params.english_ids:
            pass

        if conditions:
            base_select = base_select.where(and_(*conditions))

        return base_select

    @staticmethod
    async def get_paged_list(params: JobSearchParam) -> dict[str, Any]:
        """
        获取岗位分页列表

        :param params: 检索参数
        :return:
        """
        # 基于参数构建缓存 key
        cache_key = "job:list:" + json.dumps(
            params.model_dump(by_alias=True, exclude_none=True, exclude_unset=True),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        async with async_db_session() as db:
            select_stmt = await JobService.get_select(params)
            paginated = await apaginate(db, select_stmt)

        items = [
            JobPostingDetail.model_validate(row, from_attributes=True).model_dump(by_alias=True)
            for row in paginated.items
        ]
        page_data_dict: dict[str, Any] = {
            'items': items,
            'total': paginated.total,
            'page': paginated.page,
            'size': paginated.size,
            'total_pages': paginated.pages,
            'links': getattr(paginated, 'links', {}) or {},
        }

        # 缓存 120 秒
        await redis_client.set(cache_key, json.dumps(page_data_dict, ensure_ascii=False), ex=120)

        return page_data_dict

    @staticmethod
    async def create(obj: CreateJobPostingParam) -> None:
        """
        创建岗位

        :param obj: 创建参数
        :return:
        """
        async with async_db_session() as db:
            await job_posting_dao.create_by_schema(db, obj)
            await db.commit()
        await redis_client.delete_prefix('job:list:')

    @staticmethod
    async def update(pk: int, obj: UpdateJobPostingParam) -> int:
        """
        更新岗位

        :param pk: 岗位 ID
        :param obj: 更新参数
        :return:
        """
        async with async_db_session() as db:
            rows = await job_posting_dao.update(db, pk, obj)
            await db.commit()
        await redis_client.delete_prefix('job:list:')
        return rows

    @staticmethod
    async def delete(objs: DeleteJobPostingParam) -> int:
        """
        批量删除岗位

        :param objs: 删除参数
        :return:
        """
        if not objs.ids:
            raise errors.BadRequestError(msg='ID 列表不能为空')

        async with async_db_session() as db:
            rows = await job_posting_dao.delete(db, objs.ids)
            await db.commit()
        await redis_client.delete_prefix('job:list:')
        return rows


