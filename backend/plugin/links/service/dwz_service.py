#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.plugin.links.crud import dwz_dao, log_dao
from backend.plugin.links.model import Dwz
from backend.plugin.links.schema import CreateDwzParam, CreateLogParam, LogStatistics, UpdateDwzParam
from backend.plugin.links.service.utils import generate_random_code, parse_device, parse_reference

# 日志类型常量
LOG_TYPE_DWZ = 1


class DwzService:
    """短网址服务"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Dwz:
        """
        获取短网址详情

        :param db: 数据库会话
        :param pk: 短网址ID
        :return:
        """
        dwz = await dwz_dao.get(db, pk)
        if not dwz:
            raise errors.NotFoundError(msg='短网址不存在')
        return dwz

    @staticmethod
    async def get_by_code(*, db: AsyncSession, code: str) -> Dwz | None:
        """
        通过短码获取短网址

        :param db: 数据库会话
        :param code: 短网址Key
        :return:
        """
        return await dwz_dao.get_by_code(db, code)

    @staticmethod
    def get_select(
        *,
        title: str | None = None,
        status: int | None = None,
        created_by: int | None = None,
    ) -> Select:
        """
        获取短网址列表查询

        :param title: 标题模糊搜索
        :param status: 状态筛选
        :param created_by: 创建者筛选
        :return:
        """
        return dwz_dao.get_select(title=title, status=status, created_by=created_by)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateDwzParam, created_by: int) -> Dwz:
        """
        创建短网址

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID
        :return:
        """
        # 使用自定义短码或生成随机短码
        if obj.code:
            code = obj.code
            if await dwz_dao.check_code_exists(db, code):
                raise errors.RequestError(msg='短码已存在')
        else:
            # 生成随机短码，确保唯一性
            max_attempts = 10
            for _ in range(max_attempts):
                code = generate_random_code(6)
                if not await dwz_dao.check_code_exists(db, code):
                    break
            else:
                raise errors.ServerError(msg='短码生成失败，请重试')

        return await dwz_dao.create(db, obj, code, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateDwzParam) -> int:
        """
        更新短网址

        :param db: 数据库会话
        :param pk: 短网址ID
        :param obj: 更新参数
        :return:
        """
        dwz = await dwz_dao.get(db, pk)
        if not dwz:
            raise errors.NotFoundError(msg='短网址不存在')
        return await dwz_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除短网址

        :param db: 数据库会话
        :param pk: 短网址ID
        :return:
        """
        dwz = await dwz_dao.get(db, pk)
        if not dwz:
            raise errors.NotFoundError(msg='短网址不存在')
        # 删除相关日志
        await log_dao.delete_by_target(db, LOG_TYPE_DWZ, pk)
        return await dwz_dao.delete(db, pk)

    @staticmethod
    async def redirect(
        *,
        db: AsyncSession,
        code: str,
        request_info: dict,
        current_domain: str | None = None,
    ) -> str:
        """
        短链重定向（支持三层域名跳转）

        :param db: 数据库会话
        :param code: 短网址Key
        :param request_info: 请求信息(ip, user_agent, referer, country, city)
        :param current_domain: 当前请求的域名，用于判断跳转层级
        :return:
        """
        dwz = await dwz_dao.get_by_code(db, code)
        if not dwz:
            raise errors.NotFoundError(msg='短网址不存在')

        if dwz.status != 1:
            raise errors.RequestError(msg='短网址已停用')

        if dwz.domain_status != 1:
            raise errors.RequestError(msg='链接暂时不可用')

        # 增加访问量
        await dwz_dao.increment_clicks(db, dwz.id)

        # 记录访问日志
        user_agent = request_info.get('user_agent')
        referer = request_info.get('referer')
        log_param = CreateLogParam(
            type=LOG_TYPE_DWZ,
            target_id=dwz.id,
            ip=request_info.get('ip'),
            device=parse_device(user_agent),
            reference=parse_reference(user_agent, referer),
            user_agent=user_agent[:512] if user_agent and len(user_agent) > 512 else user_agent,
            country=request_info.get('country'),
            city=request_info.get('city'),
        )
        await log_dao.create(db, log_param)

        # 三层域名跳转逻辑
        # 如果配置了中转域名，且当前请求来自入口域名，则先跳转到中转域名
        if (
            dwz.redirect_domain
            and dwz.entry_domain
            and current_domain
            and current_domain == dwz.entry_domain
            and dwz.redirect_domain != dwz.entry_domain
        ):
            return f'https://{dwz.redirect_domain}/c/{code}'

        # 否则直接跳转到原网址（落地域名）
        return dwz.original_url

    @staticmethod
    async def get_statistics(*, db: AsyncSession, pk: int) -> LogStatistics:
        """
        获取短网址统计数据

        :param db: 数据库会话
        :param pk: 短网址ID
        :return:
        """
        dwz = await dwz_dao.get(db, pk)
        if not dwz:
            raise errors.NotFoundError(msg='短网址不存在')

        total_clicks = await log_dao.count_total(db, LOG_TYPE_DWZ, pk)
        today_clicks = await log_dao.count_today(db, LOG_TYPE_DWZ, pk)
        device_stats = await log_dao.get_device_stats(db, LOG_TYPE_DWZ, pk)
        reference_stats = await log_dao.get_reference_stats(db, LOG_TYPE_DWZ, pk)

        return LogStatistics(
            total_clicks=total_clicks or dwz.clicks,
            today_clicks=today_clicks,
            device_stats=device_stats,
            reference_stats=reference_stats,
        )


dwz_service: DwzService = DwzService()
