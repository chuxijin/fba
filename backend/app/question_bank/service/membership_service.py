#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.crud.crud_question import question_dao
from backend.common.exception import errors


class MembershipService:
    """会员权限服务（精简版，会员校验后续补充）"""

    @staticmethod
    async def verify_bank_access(*, db: AsyncSession, user_id: int, bank_id: int) -> None:
        """
        验证用户是否有访问题库的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        """
        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')
        # TODO: 会员权限校验（当前阶段全部放行）

    @staticmethod
    async def verify_chapter_access(*, db: AsyncSession, user_id: int, chapter_id: int) -> None:
        """
        验证用户是否有访问章节的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param chapter_id: 章节 ID
        """
        chapter = await chapter_dao.get(db, chapter_id)
        if not chapter:
            raise errors.NotFoundError(msg='章节不存在')

    @staticmethod
    async def verify_question_access(*, db: AsyncSession, user_id: int, question_id: int) -> None:
        """
        验证用户是否有访问题目的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        """
        question = await question_dao.get(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')

    @staticmethod
    async def verify_bank_list_access(*, db: AsyncSession, user_id: int, bank_id: int) -> None:
        """
        验证用户是否有访问题库题目列表的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        """
        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')


membership_service = MembershipService()
