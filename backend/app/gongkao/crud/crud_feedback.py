#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model.feedback import GkFeedback
from backend.app.gongkao.schema.feedback import CreateFeedbackParam, FeedbackParam, UpdateFeedbackParam


class CRUDFeedback(CRUDPlus[GkFeedback]):
    """反馈数据库操作类"""

    async def get_select(self, params: FeedbackParam) -> 'Select':
        """
        获取反馈列表查询表达式

        :param params: 查询参数
        :return:
        """
        filters = {}
        if params.type is not None:
            filters['type'] = params.type
        if params.status is not None:
            filters['status'] = params.status
        if params.content is not None:
            filters['content__like'] = f'%{params.content}%'
        if params.contact is not None:
            filters['contact__like'] = f'%{params.contact}%'
        if params.view_status is not None:
            filters['view_status'] = params.view_status

        return await self.select_order('created_time', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: CreateFeedbackParam, ip_address: str | None = None) -> GkFeedback:
        """
        创建反馈

        :param db: 数据库会话
        :param obj: 创建参数
        :param ip_address: IP 地址
        :return:
        """
        obj_dict = obj.model_dump()
        if ip_address:
            obj_dict['ip_address'] = ip_address
        feedback = await self.create_model(db, obj_dict)
        return feedback

    async def update(self, db: AsyncSession, pk: int, obj: UpdateFeedbackParam) -> int:
        """
        更新反馈

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        删除反馈（支持批量）

        :param db: 数据库会话
        :param pks: 主键 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)


feedback_dao: CRUDFeedback = CRUDFeedback(GkFeedback)
