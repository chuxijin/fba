from typing import Annotated

from fastapi import APIRouter, Body

from backend.plugin.oc.schema.crawler import CrawlerParam, CrawlerResult
from backend.plugin.oc.service.crawler_service import crawler
from backend.common.response.response_code import CustomResponseCode
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

router = APIRouter()


@router.post('', summary='爬取岗位数据', description='从 GiveMeOC 网站爬取校招或实习岗位数据')
async def crawl_jobs(
    db: CurrentSession,
    param: Annotated[CrawlerParam, Body(description='爬虫参数')],
) -> ResponseSchemaModel[CrawlerResult]:
    """
    爬取岗位数据

    :param db: 数据库会话
    :param param: 爬虫参数
    :return: 爬取结果统计
    """
    # 验证参数
    if param.end_page < param.start_page:
        return response_base.fail(code=CustomResponseCode.HTTP_400, msg='结束页码不能小于开始页码')

    if param.job_type not in ['campus', 'intern']:
        return response_base.fail(code=CustomResponseCode.HTTP_400, msg='岗位类型必须是 campus 或 intern')

    # 执行爬虫
    result = await crawler.crawl_and_save(
        db=db,
        start_page=param.start_page,
        end_page=param.end_page,
        job_type=param.job_type,
        delay=param.delay,
        nonce=param.nonce,
        cookie=param.cookie,
    )

    return response_base.success(data=result)
