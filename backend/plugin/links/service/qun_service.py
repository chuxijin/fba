#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.plugin.links.crud import log_dao, qun_dao, qun_item_dao
from backend.plugin.links.model import Qun, QunItem
from backend.plugin.links.schema import (
    CreateLogParam,
    CreateQunItemParam,
    CreateQunParam,
    LogStatistics,
    UpdateQunItemParam,
    UpdateQunParam,
)
from backend.plugin.links.service.utils import generate_random_code, parse_device, parse_reference

# 日志类型常量
LOG_TYPE_QUN = 2


class QunService:
    """群活码服务"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Qun:
        """
        获取群活码详情

        :param db: 数据库会话
        :param pk: 群活码ID
        :return:
        """
        qun = await qun_dao.get(db, pk)
        if not qun:
            raise errors.NotFoundError(msg='群活码不存在')
        return qun

    @staticmethod
    async def get_by_code(*, db: AsyncSession, code: str) -> Qun | None:
        """
        通过活码Key获取群活码

        :param db: 数据库会话
        :param code: 活码Key
        :return:
        """
        return await qun_dao.get_by_code(db, code)

    @staticmethod
    def get_select(
        *,
        title: str | None = None,
        status: int | None = None,
        created_by: int | None = None,
    ) -> Select:
        """
        获取群活码列表查询

        :param title: 标题模糊搜索
        :param status: 状态筛选
        :param created_by: 创建者筛选
        :return:
        """
        return qun_dao.get_select(title=title, status=status, created_by=created_by)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateQunParam, created_by: int) -> Qun:
        """
        创建群活码

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID
        :return:
        """
        # 使用自定义短码或生成随机短码
        if obj.code:
            code = obj.code
            if await qun_dao.check_code_exists(db, code):
                raise errors.RequestError(msg='活码Key已存在')
        else:
            max_attempts = 10
            for _ in range(max_attempts):
                code = generate_random_code(6)
                if not await qun_dao.check_code_exists(db, code):
                    break
            else:
                raise errors.ServerError(msg='活码Key生成失败，请重试')

        return await qun_dao.create(db, obj, code, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateQunParam) -> int:
        """
        更新群活码

        :param db: 数据库会话
        :param pk: 群活码ID
        :param obj: 更新参数
        :return:
        """
        qun = await qun_dao.get(db, pk)
        if not qun:
            raise errors.NotFoundError(msg='群活码不存在')
        return await qun_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除群活码

        :param db: 数据库会话
        :param pk: 群活码ID
        :return:
        """
        qun = await qun_dao.get(db, pk)
        if not qun:
            raise errors.NotFoundError(msg='群活码不存在')
        # 删除相关日志
        await log_dao.delete_by_target(db, LOG_TYPE_QUN, pk)
        return await qun_dao.delete(db, pk)

    @staticmethod
    async def redirect(
        *,
        db: AsyncSession,
        code: str,
        request_info: dict,
    ) -> QunItem:
        """
        群活码访问（获取可用的群二维码）

        :param db: 数据库会话
        :param code: 活码Key
        :param request_info: 请求信息
        :return:
        """
        qun = await qun_dao.get_by_code(db, code)
        if not qun:
            raise errors.NotFoundError(msg='群活码不存在')

        if qun.status != 1:
            raise errors.RequestError(msg='群活码已停用')

        if qun.domain_status != 1:
            raise errors.RequestError(msg='链接暂时不可用')

        # 获取可用的群二维码
        item = await qun_item_dao.get_available_item(db, qun.id)
        if not item:
            raise errors.RequestError(msg='暂无可用群二维码')

        # 增加访问量
        await qun_dao.increment_clicks(db, qun.id)
        await qun_item_dao.increment_clicks(db, item.id)

        # 检查是否达到阈值
        if item.clicks + 1 >= item.limit:
            await qun_item_dao.mark_as_full(db, item.id)

        # 记录访问日志
        user_agent = request_info.get('user_agent')
        referer = request_info.get('referer')
        log_param = CreateLogParam(
            type=LOG_TYPE_QUN,
            target_id=qun.id,
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
        :param item_id: 群二维码子项ID
        :return:
        """
        item = await qun_item_dao.get(db, item_id)
        if item:
            await qun_item_dao.increment_longpress(db, item_id)

    @staticmethod
    async def get_statistics(*, db: AsyncSession, pk: int) -> LogStatistics:
        """
        获取群活码统计数据

        :param db: 数据库会话
        :param pk: 群活码ID
        :return:
        """
        qun = await qun_dao.get(db, pk)
        if not qun:
            raise errors.NotFoundError(msg='群活码不存在')

        total_clicks = await log_dao.count_total(db, LOG_TYPE_QUN, pk)
        today_clicks = await log_dao.count_today(db, LOG_TYPE_QUN, pk)
        device_stats = await log_dao.get_device_stats(db, LOG_TYPE_QUN, pk)
        reference_stats = await log_dao.get_reference_stats(db, LOG_TYPE_QUN, pk)

        return LogStatistics(
            total_clicks=total_clicks or qun.clicks,
            today_clicks=today_clicks,
            device_stats=device_stats,
            reference_stats=reference_stats,
        )


class QunItemService:
    """群活码子项服务"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> QunItem:
        """
        获取群活码子项详情

        :param db: 数据库会话
        :param pk: 子项ID
        :return:
        """
        item = await qun_item_dao.get(db, pk)
        if not item:
            raise errors.NotFoundError(msg='群二维码不存在')
        return item

    @staticmethod
    async def get_by_qun_id(*, db: AsyncSession, qun_id: int) -> list[QunItem]:
        """
        获取群活码的所有子项

        :param db: 数据库会话
        :param qun_id: 群活码ID
        :return:
        """
        return await qun_item_dao.get_by_qun_id(db, qun_id)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateQunItemParam, created_by: int) -> QunItem:
        """
        创建群活码子项

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID
        :return:
        """
        # 验证群活码存在
        qun = await qun_dao.get(db, obj.qun_id)
        if not qun:
            raise errors.NotFoundError(msg='群活码不存在')

        return await qun_item_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateQunItemParam) -> int:
        """
        更新群活码子项

        :param db: 数据库会话
        :param pk: 子项ID
        :param obj: 更新参数
        :return:
        """
        item = await qun_item_dao.get(db, pk)
        if not item:
            raise errors.NotFoundError(msg='群二维码不存在')
        return await qun_item_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除群活码子项

        :param db: 数据库会话
        :param pk: 子项ID
        :return:
        """
        item = await qun_item_dao.get(db, pk)
        if not item:
            raise errors.NotFoundError(msg='群二维码不存在')
        return await qun_item_dao.delete(db, pk)


qun_service: QunService = QunService()
qun_item_service: QunItemService = QunItemService()
