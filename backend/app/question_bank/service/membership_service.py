#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.crud.crud_membership import membership_dao
from backend.app.question_bank.crud.crud_question import question_dao
from backend.common.exception import errors


class MembershipService:
    @staticmethod
    async def verify_bank_access(*, db: AsyncSession, user_id: int, bank_id: int) -> None:
        """
        验证用户是否有访问题库的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        """
        # 检查题库是否存在
        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')

        # 检查题库 scope：1=免费，2=付费
        if bank.scope == 1:
            return  # 免费题库，直接通过

        # 检查用户是否有会员权限
        has_access = await membership_dao.check_user_access(db=db, user_id=user_id, category=1, res_id=bank_id)
        if not has_access:
            raise errors.AuthorizationError(msg='您还没有开通该题库会员，无法访问')

    @staticmethod
    async def verify_chapter_access(*, db: AsyncSession, user_id: int, chapter_id: int) -> None:
        """
        验证用户是否有访问章节的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param chapter_id: 章节 ID
        """
        # 检查章节是否存在
        chapter = await chapter_dao.get(db, chapter_id)
        if not chapter:
            raise errors.NotFoundError(msg='章节不存在')

        # 检查题库 scope：1=免费，2=付费
        if chapter.bank.scope == 1:
            return  # 免费题库，直接通过

        # 检查章节是否为试用章节
        if chapter.is_trial:
            return  # 试用章节，直接通过

        # 检查用户是否有会员权限
        has_access = await membership_dao.check_user_access(db=db, user_id=user_id, category=1, res_id=chapter.bank_id)
        if not has_access:
            raise errors.AuthorizationError(msg='您还没有开通该题库会员，无法访问章节')

    @staticmethod
    async def verify_question_access(*, db: AsyncSession, user_id: int, question_id: int) -> None:
        """
        验证用户是否有访问题目的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        """
        # 检查题目是否存在
        question = await question_dao.get(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')

        # 获取题库信息
        bank = await bank_dao.get(db, question.bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')

        # 检查题库 scope：1=免费，2=付费
        if bank.scope == 1:
            return  # 免费题库，直接通过

        # 如果题目有章节，检查章节是否为试用章节
        if question.chapter_id:
            chapter = await chapter_dao.get(db, question.chapter_id)
            if chapter and chapter.is_trial:
                return  # 试用章节的题目，直接通过

        # 检查用户是否有会员权限
        has_access = await membership_dao.check_user_access(db=db, user_id=user_id, category=1, res_id=question.bank_id)
        if not has_access:
            raise errors.AuthorizationError(msg='您还没有开通该题库会员，无法访问题目')

    @staticmethod
    async def verify_bank_list_access(*, db: AsyncSession, user_id: int, bank_id: int) -> None:
        """
        验证用户是否有访问题库中的题目列表的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        """
        # 检查题库是否存在
        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')

        # 检查题库 scope：1=免费，2=付费
        if bank.scope == 1:
            return  # 免费题库，直接通过

        # 检查用户是否有会员权限
        has_access = await membership_dao.check_user_access(db=db, user_id=user_id, category=1, res_id=bank_id)
        if not has_access:
            raise errors.AuthorizationError(msg='您还没有开通该题库会员，无法访问题目列表')


membership_service = MembershipService()
