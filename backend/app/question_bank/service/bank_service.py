#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_category import category_dao
from backend.app.question_bank.model import QuestionBank
from backend.app.question_bank.schema.bank import CreateBankParam, DeleteBankParam, UpdateBankParam
from backend.common.exception import errors
from backend.utils.build_tree import get_tree_data


class BankService:
    """题库服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> QuestionBank:
        """
        获取题库详情

        :param db: 数据库会话
        :param pk: 题库 ID
        :return:
        """
        bank = await bank_dao.get(db, pk)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')
        return bank

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        cat_id: int | None = None,
        status: int | None = None,
        scope: int | None = None,
        keyword: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取题库树形列表

        :param db: 数据库会话
        :param cat_id: 分类 ID
        :param status: 题库状态
        :param scope: 可见范围
        :param keyword: 关键字搜索
        :return:
        """
        bank_select = await bank_dao.get_all(db, cat_id, status, scope, keyword)
        tree_data = get_tree_data(bank_select, sort_key='id')
        return tree_data

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateBankParam) -> None:
        """
        创建题库

        :param db: 数据库会话
        :param obj: 创建题库参数
        :return:
        """
        bank = await bank_dao.get_by_code(db, obj.code)
        if bank:
            raise errors.ConflictError(msg='题库编码已存在')
        category = await category_dao.get(db, obj.cat_id)
        if not category:
            raise errors.NotFoundError(msg='所属分类不存在')
        await bank_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateBankParam) -> int:
        """
        更新题库

        :param db: 数据库会话
        :param pk: 题库 ID
        :param obj: 更新题库参数
        :return:
        """
        bank = await bank_dao.get(db, pk)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')
        if bank.code != obj.code and await bank_dao.get_by_code(db, obj.code):
            raise errors.ConflictError(msg='题库编码已存在')
        category = await category_dao.get(db, obj.cat_id)
        if not category:
            raise errors.NotFoundError(msg='所属分类不存在')
        count = await bank_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteBankParam) -> int:
        """
        删除题库

        :param db: 数据库会话
        :param obj: 删除题库参数
        :return:
        """
        count = await bank_dao.delete(db, obj.ids)
        return count


bank_service: BankService = BankService()
