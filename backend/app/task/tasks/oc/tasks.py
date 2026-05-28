#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from celery import shared_task

from backend.common.log import log
from backend.database.db import async_db_session
from backend.utils.dynamic_config import load_crawler_config
from backend.core.conf import settings


@shared_task
async def crawl_jobs_task(job_type: str = 'campus') -> str:
    """
    爬取岗位数据定时任务

    :param job_type: 岗位类型（campus=校招, intern=实习）
    :return: 任务结果
    """
    from backend.plugin.oc.service.crawler_service import crawler
    from backend.plugin.email.utils.send import send_email

    async with async_db_session.begin() as db:
        await load_crawler_config(db)

        cookie = getattr(settings, 'CRAWLER_COOKIE', '') or None
        notify_email = getattr(settings, 'CRAWLER_NOTIFY_EMAIL', '')

        job_type_name = '校招' if job_type == 'campus' else '实习'
        log.info(f'[定时任务] 开始爬取{job_type_name}数据...')

        try:
            result = await crawler.crawl_and_save(
                db=db,
                start_page=1,
                end_page=2,
                job_type=job_type,
                delay=1.0,
                nonce=None,
                cookie=cookie,
            )

            if result.get('errors'):
                error_msg = f'[定时任务] {job_type_name}爬取完成但有错误:\n' + '\n'.join(result['errors'][:5])
                log.warning(error_msg)

                if notify_email:
                    try:
                        await send_email(
                            db=db,
                            recipients=notify_email,
                            subject=f'[GetOC] {job_type_name}爬虫任务异常通知',
                            content=f"""
爬虫任务执行完成，但存在以下问题：

任务类型：{job_type_name}
爬取数量：{result.get('total_crawled', 0)}
保存数量：{result.get('total_saved', 0)}
跳过数量：{result.get('total_skipped', 0)}

错误信息：
{chr(10).join(result['errors'][:10])}

请及时检查！
                            """,
                        )
                        log.info(f'已发送异常通知邮件到 {notify_email}')
                    except Exception as e:
                        log.error(f'发送通知邮件失败: {e}')

            success_msg = (
                f'[定时任务] {job_type_name}爬取完成 - '
                f'爬取: {result.get("total_crawled", 0)}, '
                f'保存: {result.get("total_saved", 0)}, '
                f'跳过: {result.get("total_skipped", 0)}'
            )
            log.info(success_msg)
            return success_msg

        except Exception as e:
            error_msg = f'[定时任务] {job_type_name}爬取失败: {e}'
            log.error(error_msg)

            if notify_email:
                try:
                    await send_email(
                        db=db,
                        recipients=notify_email,
                        subject=f'[GetOC] {job_type_name}爬虫任务失败通知',
                        content=f"""
爬虫任务执行失败！

任务类型：{job_type_name}
错误信息：{e}

可能的原因：
1. 网站无法访问
2. Cookie 已过期，请更新配置
3. 网站结构发生变化

请及时检查并处理！
                        """,
                    )
                    log.info(f'已发送失败通知邮件到 {notify_email}')
                except Exception as mail_error:
                    log.error(f'发送通知邮件失败: {mail_error}')

            raise


@shared_task
async def crawl_all_jobs_task() -> str:
    """爬取所有类型的岗位数据（校招+实习）"""
    campus_result = await crawl_jobs_task('campus')
    intern_result = await crawl_jobs_task('intern')
    return f'校招: {campus_result}\n实习: {intern_result}'
