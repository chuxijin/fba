#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.task.celery import celery_app

from backend.common.log import log
from backend.database.db import async_db_session
from backend.utils.dynamic_config import load_crawler_config
from backend.core.conf import settings


@celery_app.task(name='crawl_jobs_task', bind=True)
async def crawl_jobs_task(self, job_type: str = 'campus') -> str:
    """
    爬取岗位数据定时任务

    :param job_type: 岗位类型（campus=校招, intern=实习）
    :return: 任务结果
    """
    from backend.plugin.oc.service.crawler_service import crawler

    async with async_db_session.begin() as db:
        await load_crawler_config(db)

        cookie = getattr(settings, 'CRAWLER_COOKIE', '') or None

        job_type_name = '校招' if job_type == 'campus' else '实习'
        log.info(f'[定时任务] 开始爬取{job_type_name}数据...')

        result = await crawler.crawl_and_save(
            db=db,
            start_page=1,
            end_page=3,
            job_type=job_type,
            delay=1.0,
            nonce=None,
            cookie=cookie,
        )

        if result.get('errors'):
            error_detail = '\n'.join(result['errors'][:5])
            log.warning(f'[定时任务] {job_type_name}爬取完成但有错误:\n{error_detail}')
            await self.on_warning(
                f'{job_type_name}爬取完成但有部分错误，'
                f'爬取: {result.get("total_crawled", 0)}, '
                f'保存: {result.get("total_saved", 0)}, '
                f'跳过: {result.get("total_skipped", 0)}\n'
                f'错误: {error_detail}'
            )

        success_msg = (
            f'[定时任务] {job_type_name}爬取完成 - '
            f'爬取: {result.get("total_crawled", 0)}, '
            f'保存: {result.get("total_saved", 0)}, '
            f'跳过: {result.get("total_skipped", 0)}'
        )
        log.info(success_msg)
        return success_msg


@celery_app.task(name='crawl_all_jobs_task', bind=True)
async def crawl_all_jobs_task(self) -> str:
    """爬取所有类型的岗位数据（校招+实习）"""
    campus_result = await crawl_jobs_task('campus')
    intern_result = await crawl_jobs_task('intern')
    return f'校招: {campus_result}\n实习: {intern_result}'
