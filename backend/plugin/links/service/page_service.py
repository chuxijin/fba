#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.plugin.links.crud import log_dao, page_dao
from backend.plugin.links.model import Page
from backend.plugin.links.schema import CreateLogParam, CreatePageParam, LogStatistics, UpdatePageParam
from backend.plugin.links.service.utils import generate_random_code, parse_device, parse_reference

# 日志类型常量
LOG_TYPE_PAGE = 4


class PageService:
    """静态页面服务"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Page:
        """
        获取页面详情

        :param db: 数据库会话
        :param pk: 页面ID
        :return:
        """
        page = await page_dao.get(db, pk)
        if not page:
            raise errors.NotFoundError(msg='页面不存在')
        return page

    @staticmethod
    async def get_by_code(*, db: AsyncSession, code: str) -> Page | None:
        """
        通过短码获取页面

        :param db: 数据库会话
        :param code: 页面Key
        :return:
        """
        return await page_dao.get_by_code(db, code)

    @staticmethod
    def get_select(
        *,
        title: str | None = None,
        status: int | None = None,
        created_by: int | None = None,
    ) -> Select:
        """
        获取页面列表查询

        :param title: 标题模糊搜索
        :param status: 状态筛选
        :param created_by: 创建者筛选
        :return:
        """
        return page_dao.get_select(title=title, status=status, created_by=created_by)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreatePageParam, created_by: int) -> Page:
        """
        创建页面

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID
        :return:
        """
        if obj.code:
            code = obj.code
            if await page_dao.check_code_exists(db, code):
                raise errors.RequestError(msg='短码已存在')
        else:
            max_attempts = 10
            for _ in range(max_attempts):
                code = generate_random_code(6)
                if not await page_dao.check_code_exists(db, code):
                    break
            else:
                raise errors.ServerError(msg='短码生成失败，请重试')

        return await page_dao.create(db, obj, code, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdatePageParam) -> int:
        """
        更新页面

        :param db: 数据库会话
        :param pk: 页面ID
        :param obj: 更新参数
        :return:
        """
        page = await page_dao.get(db, pk)
        if not page:
            raise errors.NotFoundError(msg='页面不存在')
        return await page_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除页面

        :param db: 数据库会话
        :param pk: 页面ID
        :return:
        """
        page = await page_dao.get(db, pk)
        if not page:
            raise errors.NotFoundError(msg='页面不存在')
        await log_dao.delete_by_target(db, LOG_TYPE_PAGE, pk)
        return await page_dao.delete(db, pk)

    @staticmethod
    async def render(*, db: AsyncSession, code: str, request_info: dict) -> Page:
        """
        渲染页面：校验状态、增加访问量、记录日志，返回 Page 对象供 api 层产出 HTML

        :param db: 数据库会话
        :param code: 页面Key
        :param request_info: 请求信息(ip, user_agent, referer, country, city)
        :return:
        """
        page = await page_dao.get_by_code(db, code)
        if not page:
            raise errors.NotFoundError(msg='页面不存在')

        if page.status != 1:
            raise errors.RequestError(msg='页面已停用')

        if page.domain_status != 1:
            raise errors.RequestError(msg='页面暂时不可用')

        await page_dao.increment_clicks(db, page.id)

        user_agent = request_info.get('user_agent')
        referer = request_info.get('referer')
        log_param = CreateLogParam(
            type=LOG_TYPE_PAGE,
            target_id=page.id,
            ip=request_info.get('ip'),
            device=parse_device(user_agent),
            reference=parse_reference(user_agent, referer),
            user_agent=user_agent[:512] if user_agent and len(user_agent) > 512 else user_agent,
            country=request_info.get('country'),
            city=request_info.get('city'),
        )
        await log_dao.create(db, log_param)

        return page

    @staticmethod
    async def get_statistics(*, db: AsyncSession, pk: int) -> LogStatistics:
        """
        获取页面统计数据

        :param db: 数据库会话
        :param pk: 页面ID
        :return:
        """
        page = await page_dao.get(db, pk)
        if not page:
            raise errors.NotFoundError(msg='页面不存在')

        total_clicks = await log_dao.count_total(db, LOG_TYPE_PAGE, pk)
        today_clicks = await log_dao.count_today(db, LOG_TYPE_PAGE, pk)
        device_stats = await log_dao.get_device_stats(db, LOG_TYPE_PAGE, pk)
        reference_stats = await log_dao.get_reference_stats(db, LOG_TYPE_PAGE, pk)

        return LogStatistics(
            total_clicks=total_clicks or page.clicks,
            today_clicks=today_clicks,
            device_stats=device_stats,
            reference_stats=reference_stats,
        )


page_service: PageService = PageService()
