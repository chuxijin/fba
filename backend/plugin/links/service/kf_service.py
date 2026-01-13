#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.plugin.links.crud import kf_dao, kf_item_dao, log_dao
from backend.plugin.links.model import Kf, KfItem
from backend.plugin.links.schema import (
    CreateKfItemParam,
    CreateKfParam,
    CreateLogParam,
    LogStatistics,
    UpdateKfItemParam,
    UpdateKfParam,
)
from backend.plugin.links.service.utils import generate_random_code, parse_device, parse_reference

# 日志类型常量
LOG_TYPE_KF = 3


class KfService:
    """客服码服务"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Kf:
        """
        获取客服码详情

        :param db: 数据库会话
        :param pk: 客服码ID
        :return:
        """
        kf = await kf_dao.get(db, pk)
        if not kf:
            raise errors.NotFoundError(msg='客服码不存在')
        return kf

    @staticmethod
    async def get_by_code(*, db: AsyncSession, code: str) -> Kf | None:
        """
        通过客服码Key获取客服码

        :param db: 数据库会话
        :param code: 客服码Key
        :return:
        """
        return await kf_dao.get_by_code(db, code)

    @staticmethod
    def get_select(
        *,
        title: str | None = None,
        status: int | None = None,
        created_by: int | None = None,
    ) -> Select:
        """
        获取客服码列表查询

        :param title: 标题模糊搜索
        :param status: 状态筛选
        :param created_by: 创建者筛选
        :return:
        """
        return kf_dao.get_select(title=title, status=status, created_by=created_by)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateKfParam, created_by: int) -> Kf:
        """
        创建客服码

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID
        :return:
        """
        # 使用自定义短码或生成随机短码
        if obj.code:
            code = obj.code
            if await kf_dao.check_code_exists(db, code):
                raise errors.RequestError(msg='客服码Key已存在')
        else:
            max_attempts = 10
            for _ in range(max_attempts):
                code = generate_random_code(6)
                if not await kf_dao.check_code_exists(db, code):
                    break
            else:
                raise errors.ServerError(msg='客服码Key生成失败，请重试')

        return await kf_dao.create(db, obj, code, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateKfParam) -> int:
        """
        更新客服码

        :param db: 数据库会话
        :param pk: 客服码ID
        :param obj: 更新参数
        :return:
        """
        kf = await kf_dao.get(db, pk)
        if not kf:
            raise errors.NotFoundError(msg='客服码不存在')
        return await kf_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除客服码

        :param db: 数据库会话
        :param pk: 客服码ID
        :return:
        """
        kf = await kf_dao.get(db, pk)
        if not kf:
            raise errors.NotFoundError(msg='客服码不存在')
        # 删除相关日志
        await log_dao.delete_by_target(db, LOG_TYPE_KF, pk)
        return await kf_dao.delete(db, pk)

    @staticmethod
    async def redirect(
        *,
        db: AsyncSession,
        code: str,
        request_info: dict,
    ) -> KfItem:
        """
        客服码访问（获取可用的客服二维码）

        :param db: 数据库会话
        :param code: 客服码Key
        :param request_info: 请求信息
        :return:
        """
        kf = await kf_dao.get_by_code(db, code)
        if not kf:
            raise errors.NotFoundError(msg='客服码不存在')

        if kf.status != 1:
            raise errors.RequestError(msg='客服码已停用')

        if kf.domain_status != 1:
            raise errors.RequestError(msg='链接暂时不可用')

        # 获取可用的客服二维码
        item = await kf_item_dao.get_available_item(db, kf.id)
        if not item:
            raise errors.RequestError(msg='暂无可用客服二维码')

        # 增加访问量
        await kf_dao.increment_clicks(db, kf.id)
        await kf_item_dao.increment_clicks(db, item.id)

        # 检查是否达到阈值
        if item.clicks + 1 >= item.limit:
            await kf_item_dao.mark_as_full(db, item.id)

        # 记录访问日志
        user_agent = request_info.get('user_agent')
        referer = request_info.get('referer')
        log_param = CreateLogParam(
            type=LOG_TYPE_KF,
            target_id=kf.id,
            ip=request_info.get('ip'),
            device=parse_device(user_agent),
            reference=parse_reference(user_agent, referer),
            user_agent=user_agent[:512] if user_agent and len(user_agent) > 512 else user_agent,
            country=request_info.get('country'),
            city=request_info.get('city'),
        )
        await log_dao.create(db, log_param)

        return item

    @staticmethod
    async def record_longpress(*, db: AsyncSession, item_id: int) -> None:
        """
        记录长按（扫码）行为

        :param db: 数据库会话
        :param item_id: 客服二维码子项ID
        :return:
        """
        item = await kf_item_dao.get(db, item_id)
        if item:
            await kf_item_dao.increment_longpress(db, item_id)

    @staticmethod
    async def get_statistics(*, db: AsyncSession, pk: int) -> LogStatistics:
        """
        获取客服码统计数据

        :param db: 数据库会话
        :param pk: 客服码ID
        :return:
        """
        kf = await kf_dao.get(db, pk)
        if not kf:
            raise errors.NotFoundError(msg='客服码不存在')

        total_clicks = await log_dao.count_total(db, LOG_TYPE_KF, pk)
        today_clicks = await log_dao.count_today(db, LOG_TYPE_KF, pk)
        device_stats = await log_dao.get_device_stats(db, LOG_TYPE_KF, pk)
        reference_stats = await log_dao.get_reference_stats(db, LOG_TYPE_KF, pk)

        return LogStatistics(
            total_clicks=total_clicks or kf.clicks,
            today_clicks=today_clicks,
            device_stats=device_stats,
            reference_stats=reference_stats,
        )


class KfItemService:
    """客服码子项服务"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> KfItem:
        """
        获取客服码子项详情

        :param db: 数据库会话
        :param pk: 子项ID
        :return:
        """
        item = await kf_item_dao.get(db, pk)
        if not item:
            raise errors.NotFoundError(msg='客服二维码不存在')
        return item

    @staticmethod
    async def get_by_kf_id(*, db: AsyncSession, kf_id: int) -> list[KfItem]:
        """
        获取客服码的所有子项

        :param db: 数据库会话
        :param kf_id: 客服码ID
        :return:
        """
        return await kf_item_dao.get_by_kf_id(db, kf_id)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateKfItemParam, created_by: int) -> KfItem:
        """
        创建客服码子项

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID
        :return:
        """
        # 验证客服码存在
        kf = await kf_dao.get(db, obj.kf_id)
        if not kf:
            raise errors.NotFoundError(msg='客服码不存在')

        return await kf_item_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateKfItemParam) -> int:
        """
        更新客服码子项

        :param db: 数据库会话
        :param pk: 子项ID
        :param obj: 更新参数
        :return:
        """
        item = await kf_item_dao.get(db, pk)
        if not item:
            raise errors.NotFoundError(msg='客服二维码不存在')
        return await kf_item_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除客服码子项

        :param db: 数据库会话
        :param pk: 子项ID
        :return:
        """
        item = await kf_item_dao.get(db, pk)
        if not item:
            raise errors.NotFoundError(msg='客服二维码不存在')
        return await kf_item_dao.delete(db, pk)


kf_service: KfService = KfService()
kf_item_service: KfItemService = KfItemService()
