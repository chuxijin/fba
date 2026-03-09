#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.crud.crud_question import question_dao, question_placement_dao
from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.model import QuestionPlacement
from backend.common.exception import errors


class MembershipService:
    """会员权限服务"""

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
        # TODO: 会员等级校验（当前阶段公开题库全部放行，付费题库需要 membership 表判断）

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

    @staticmethod
    async def verify_placement_access(*, db: AsyncSession, user_id: int, placement_id: int) -> None:
        """
        验证用户是否有访问特定挂载的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param placement_id: 挂载 ID
        """
        stmt = select(QuestionPlacement).where(
            QuestionPlacement.id == placement_id,
            QuestionPlacement.is_active.is_(True),
        )
        result = await db.execute(stmt)
        placement = result.scalars().first()
        if not placement:
            raise errors.NotFoundError(msg='题目挂载不存在或已禁用')

        # 校验挂载所属题库的访问权限
        await MembershipService.verify_bank_access(db=db, user_id=user_id, bank_id=placement.bank_id)

    @staticmethod
    async def verify_session_access(*, db: AsyncSession, user_id: int, session_id: int) -> None:
        """
        验证用户是否有访问特定会话的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 会话 ID
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')

    @staticmethod
    async def verify_scene_access(*, db: AsyncSession, user_id: int, scene_mask: int) -> None:
        """
        验证用户是否有访问特定场景的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param scene_mask: 场景位掩码
        """
        # TODO: 场景权限校验（根据用户订阅的场景包判断）
        pass


membership_service = MembershipService()
