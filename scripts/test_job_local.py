#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地直连测试：验证 Job 模块 CRUD 与分页是否正常运行"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from backend.app.job.schema.job import (
    CreateJobPostingParam,
    DeleteJobPostingParam,
    JobSearchParam,
    UpdateJobPostingParam,
)
from backend.app.job.service.job import JobService
from backend.database.db import async_db_session


async def test_create() -> None:
    """
    创建一条岗位用于后续测试

    :return:
    """
    obj = CreateJobPostingParam(
        job_title='本地测试岗位',
        class_=26,
        company_name='本地测试公司',
        main_company_name='测试主体',
        company_alias='测试别名',
        org_type=['民企'],
        industry=['互联网'],
        salary='25-35K·14薪',
        responsibility='测试职责',
        raw_position_require='测试任职要求',
        position_require_parsed=True,
        position_require_new={
            'degree_bachelor': 1,
            'degree_master': 0,
            'degree_doctor': 0,
            'degree_unlimited': 0,
            'e_4': 1,
            'e_6': 0,
            's_211': 0,
            's_double_first_class': 0,
            'address': ['深圳市'],
            'major': ['计算机'],
            'class': [26],
            'address_id': [2016],
            'major_id': [441],
        },
        job_title_id=[126],
        address_id=[2016],
        major_id=[441],
        tags=['测试'],
        publish_date=datetime.utcnow(),
        expire_date=datetime.utcnow() + timedelta(days=365),
        spider_time=datetime.utcnow(),
        position_web_url='https://example.com/job/test',
        referral_code='local',
        referral_show_index=1,
    )
    await JobService.create(obj)
    print('[create] ok')


async def test_list() -> list[dict[str, Any]]:
    """
    分页查询岗位

    :return:
    """
    params = JobSearchParam(class_=0, page=1, page_size=10)
    select_stmt = await JobService.get_select(params)
    async with async_db_session() as db:
        res = await db.execute(select_stmt)
        rows = res.scalars().all()
    items = [{'id': r.id, 'job_title': r.job_title} for r in rows]
    print('[list] items_len:', len(items))
    return items


async def test_update_first(items: list[dict[str, Any]]) -> None:
    """
    更新第一条（若存在）

    :param items: 列表项
    :return:
    """
    if not items:
        print('[update] no items, skip')
        return
    pk = items[0]['id']
    rows = await JobService.update(pk, UpdateJobPostingParam(salary='30-40K·14薪', tags=['测试', '更新']))
    print('[update] rows:', rows)


async def test_delete_by_title() -> None:
    """
    删除标题为本地测试岗位的数据

    :return:
    """
    # 复用列表拿到全部，再按标题过滤需要删除的 id
    params = JobSearchParam(class_=0, page=1, page_size=100)
    select_stmt = await JobService.get_select(params)
    async with async_db_session() as db:
        res = await db.execute(select_stmt)
        rows = res.scalars().all()
    items = [{'id': r.id, 'job_title': r.job_title} for r in rows]
    ids = [it['id'] for it in items if it.get('job_title') == '本地测试岗位']
    if not ids:
        print('[delete] nothing to delete')
        return
    rows = await JobService.delete(DeleteJobPostingParam(ids=ids))
    print('[delete] rows:', rows)


async def main() -> None:
    """顺序：create -> list -> update -> list -> delete -> list"""
    await test_create()
    items = await test_list()
    await test_update_first(items)
    await test_list()
    await test_delete_by_title()
    await test_list()


if __name__ == '__main__':
    asyncio.run(main())


