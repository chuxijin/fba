#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.membership.crud.crud_entitlement import membership_entitlement_dao
from backend.app.membership.security import check_membership_entitlement
from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.crud.crud_question import question_dao
from backend.app.question_bank.model import QuestionBank, QuestionPlacement
from backend.common.exception import errors


class MembershipService:
    """题库会员权限服务"""

    QBANK_FILTER_ENTITLEMENT_CODE: str = 'qbank_premium_filter_access'
    KNOWLEDGE_ACCESS_ENTITLEMENT_CODE: str = 'knowledge_premium_access'

    @staticmethod
    def _normalize_entitlement_code(value: str | None) -> str | None:
        """标准化权益编码"""
        if value is None:
            return None

        normalized = value.strip()
        if not normalized:
            return None
        return normalized

    @staticmethod
    def _has_text_value(value: str | None) -> bool:
        """判断文本值是否有效"""
        if value is None:
            return False
        return bool(value.strip())

    @staticmethod
    def _has_iterable_value(value: Iterable[Any] | None) -> bool:
        """判断列表值是否有效"""
        if value is None:
            return False
        return any(item is not None and str(item).strip() for item in value)

    @staticmethod
    async def _get_active_bank_ids_by_chapter_source(
        *,
        db: AsyncSession,
        source_bank_id: int,
    ) -> list[int]:
        """
        获取使用指定篇章来源的有效题库 ID 列表

        :param db: 数据库会话
        :param source_bank_id: 篇章来源题库 ID
        :return:
        """
        stmt = (
            select(QuestionBank.id)
            .where(
                QuestionBank.status == 1,
                or_(
                    QuestionBank.id == source_bank_id,
                    QuestionBank.chapter_source_bank_id == source_bank_id,
                ),
            )
            .order_by(QuestionBank.id.asc())
        )
        rows = (await db.execute(stmt)).all()
        return [row[0] for row in rows]

    @classmethod
    async def _ensure_entitlement_available(cls, *, db: AsyncSession, entitlement_code: str) -> None:
        """
        确保权益配置存在且启用

        :param db: 数据库会话
        :param entitlement_code: 权益编码
        :return:
        """
        entitlement = await membership_entitlement_dao.get_by_code(db, entitlement_code)
        if not entitlement:
            raise errors.ServerError(msg=f'权益配置缺失: {entitlement_code}')
        if entitlement.status != 1:
            raise errors.ServerError(msg=f'权益配置未启用: {entitlement_code}')

    @classmethod
    async def _build_entitlement_grant_map(
        cls,
        *,
        db: AsyncSession,
        user_id: int,
        entitlement_codes: Iterable[str | None],
    ) -> dict[str, bool]:
        """
        批量计算用户对权益编码的访问结果

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_codes: 权益编码列表
        :return:
        """
        normalized_codes = sorted(
            {
                code
                for code in (cls._normalize_entitlement_code(item) for item in entitlement_codes)
                if code is not None
            }
        )
        if not normalized_codes:
            return {}

        grant_map: dict[str, bool] = {}
        for code in normalized_codes:
            await cls._ensure_entitlement_available(db=db, entitlement_code=code)
            try:
                await check_membership_entitlement(
                    db,
                    user_id=user_id,
                    entitlement_code=code,
                )
            except errors.ForbiddenError:
                grant_map[code] = False
                continue

            grant_map[code] = True

        return grant_map

    @classmethod
    async def _require_entitlement(
        cls,
        *,
        db: AsyncSession,
        user_id: int,
        entitlement_code: str,
        message: str,
    ) -> None:
        """
        要求用户具备指定权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param message: 权限不足提示
        :return:
        """
        grant_map = await cls._build_entitlement_grant_map(
            db=db,
            user_id=user_id,
            entitlement_codes=[entitlement_code],
        )
        if grant_map.get(entitlement_code):
            return

        raise errors.ForbiddenError(msg=message)

    @classmethod
    async def _verify_bank_model_access(
        cls,
        *,
        db: AsyncSession,
        user_id: int,
        bank: QuestionBank,
    ) -> None:
        """
        按题库模型校验访问权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank: 题库模型
        :return:
        """
        entitlement_code = cls._normalize_entitlement_code(bank.access_entitlement_code)
        if entitlement_code is None:
            return

        await cls._require_entitlement(
            db=db,
            user_id=user_id,
            entitlement_code=entitlement_code,
            message='当前题库需要会员权限',
        )

    @classmethod
    async def resolve_bank_context_for_chapter(
        cls,
        *,
        db: AsyncSession,
        chapter_id: int,
        bank_id: int | None = None,
        user_id: int | None = None,
    ) -> int:
        """
        解析篇章访问所对应的题库上下文

        :param db: 数据库会话
        :param chapter_id: 篇章 ID
        :param bank_id: 显式题库 ID
        :param user_id: 用户 ID，传入时会同步校验访问权限
        :return:
        """
        chapter = await chapter_dao.get(db, chapter_id)
        if not chapter:
            raise errors.NotFoundError(msg='篇章不存在')

        if bank_id is not None:
            await cls.verify_bank_chapter_relation(db=db, bank_id=bank_id, chapter_id=chapter_id)
            if user_id is not None:
                await cls.verify_bank_access(db=db, user_id=user_id, bank_id=bank_id)
            return bank_id

        candidate_bank_ids = await cls._get_active_bank_ids_by_chapter_source(
            db=db,
            source_bank_id=chapter.bank_id,
        )
        if not candidate_bank_ids:
            raise errors.NotFoundError(msg='篇章关联题库不存在')
        if len(candidate_bank_ids) > 1:
            raise errors.RequestError(msg='当前篇章被多个题库复用，请传 bank_id 明确题库上下文')

        resolved_bank_id = candidate_bank_ids[0]
        if user_id is not None:
            await cls.verify_bank_access(db=db, user_id=user_id, bank_id=resolved_bank_id)
        return resolved_bank_id

    @classmethod
    async def _get_question_access_map(
        cls,
        *,
        db: AsyncSession,
        question_ids: list[int],
    ) -> dict[int, set[str | None]]:
        """
        获取题目对应的访问权益映射

        :param db: 数据库会话
        :param question_ids: 题目 ID 列表
        :return:
        """
        if not question_ids:
            return {}

        stmt = (
            select(
                QuestionPlacement.question_id,
                QuestionBank.access_entitlement_code,
            )
            .join(QuestionBank, QuestionBank.id == QuestionPlacement.bank_id)
            .where(
                QuestionPlacement.question_id.in_(question_ids),
                QuestionPlacement.is_active.is_(True),
                QuestionBank.status == 1,
            )
        )
        rows = (await db.execute(stmt)).all()

        access_map: dict[int, set[str | None]] = defaultdict(set)
        for question_id, entitlement_code in rows:
            access_map[question_id].add(cls._normalize_entitlement_code(entitlement_code))
        return access_map

    @staticmethod
    def _ensure_question_access_by_codes(
        *,
        access_codes: set[str | None],
        grant_map: dict[str, bool],
    ) -> None:
        """
        根据题目可用资源判断是否可访问

        :param access_codes: 题目关联的权益编码集合
        :param grant_map: 用户权益结果
        :return:
        """
        if not access_codes:
            return

        protected_codes = sorted({code for code in access_codes if code is not None})
        if not protected_codes:
            return

        if None in access_codes or len(protected_codes) > 1:
            if all(grant_map.get(code, False) for code in protected_codes):
                return
            raise errors.ForbiddenError(msg='当前题目存在多个题库权限上下文，请通过已授权题库或会话访问')

        if grant_map.get(protected_codes[0], False):
            return

        raise errors.ForbiddenError(msg='当前题目需要会员权限')

    @classmethod
    async def verify_bank_access(cls, *, db: AsyncSession, user_id: int, bank_id: int) -> None:
        """
        校验用户是否有访问题库的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        :return:
        """
        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')

        await cls._verify_bank_model_access(db=db, user_id=user_id, bank=bank)

    @staticmethod
    async def verify_chapter_access(*, db: AsyncSession, user_id: int, chapter_id: int) -> None:
        """
        校验用户是否有访问篇章的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param chapter_id: 篇章 ID
        :return:
        """
        chapter = await chapter_dao.get(db, chapter_id)
        if not chapter:
            raise errors.NotFoundError(msg='篇章不存在')

        await MembershipService.verify_bank_access(db=db, user_id=user_id, bank_id=chapter.bank_id)

    @staticmethod
    async def verify_bank_chapter_relation(*, db: AsyncSession, bank_id: int, chapter_id: int) -> None:
        """
        校验篇章是否属于题库当前篇章来源

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param chapter_id: 篇章 ID
        :return:
        """
        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')

        chapter = await chapter_dao.get(db, chapter_id)
        if not chapter:
            raise errors.NotFoundError(msg='篇章不存在')

        source_bank_id = bank.chapter_source_bank_id or bank.id
        if chapter.bank_id != source_bank_id:
            raise errors.ForbiddenError(msg=f'篇章 ID {chapter_id} 不属于题库 ID {bank_id} 的篇章来源')

    @staticmethod
    async def verify_bank_chapter_access(*, db: AsyncSession, user_id: int, bank_id: int, chapter_id: int) -> None:
        """
        校验篇章与题库关系并校验访问权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        :param chapter_id: 篇章 ID
        :return:
        """
        await MembershipService.verify_bank_chapter_relation(db=db, bank_id=bank_id, chapter_id=chapter_id)
        await MembershipService.verify_bank_access(db=db, user_id=user_id, bank_id=bank_id)

    @staticmethod
    async def verify_question_access(*, db: AsyncSession, user_id: int, question_id: int) -> None:
        """
        校验用户是否有访问题目的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :return:
        """
        question = await question_dao.get(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')

        access_map = await MembershipService._get_question_access_map(db=db, question_ids=[question_id])
        grant_map = await MembershipService._build_entitlement_grant_map(
            db=db,
            user_id=user_id,
            entitlement_codes=access_map.get(question_id, set()),
        )
        MembershipService._ensure_question_access_by_codes(
            access_codes=access_map.get(question_id, set()),
            grant_map=grant_map,
        )

    @staticmethod
    async def verify_question_ids_access(*, db: AsyncSession, user_id: int, question_ids: list[int]) -> None:
        """
        批量校验题目访问权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_ids: 题目 ID 列表
        :return:
        """
        normalized_question_ids = [question_id for question_id in dict.fromkeys(question_ids) if question_id > 0]
        if not normalized_question_ids:
            return

        access_map = await MembershipService._get_question_access_map(db=db, question_ids=normalized_question_ids)
        grant_map = await MembershipService._build_entitlement_grant_map(
            db=db,
            user_id=user_id,
            entitlement_codes=[
                code
                for access_codes in access_map.values()
                for code in access_codes
            ],
        )
        for question_id in normalized_question_ids:
            MembershipService._ensure_question_access_by_codes(
                access_codes=access_map.get(question_id, set()),
                grant_map=grant_map,
            )

    @staticmethod
    async def verify_bank_list_access(*, db: AsyncSession, user_id: int, bank_id: int) -> None:
        """
        校验题库题目列表访问权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        :return:
        """
        await MembershipService.verify_bank_access(db=db, user_id=user_id, bank_id=bank_id)

    @staticmethod
    async def verify_placement_access(*, db: AsyncSession, user_id: int, placement_id: int) -> None:
        """
        校验题目挂载访问权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param placement_id: 挂载 ID
        :return:
        """
        stmt = select(QuestionPlacement).where(
            QuestionPlacement.id == placement_id,
            QuestionPlacement.is_active.is_(True),
        )
        result = await db.execute(stmt)
        placement = result.scalars().first()
        if not placement:
            raise errors.NotFoundError(msg='题目挂载不存在或已禁用')

        await MembershipService.verify_bank_access(db=db, user_id=user_id, bank_id=placement.bank_id)

    @classmethod
    async def verify_filter_access(
        cls,
        *,
        db: AsyncSession,
        user_id: int,
        cat_id: int | None = None,
        region: str | None = None,
        year_start: int | None = None,
        year_end: int | None = None,
        stem_keyword: str | None = None,
        option_keyword: str | None = None,
        analysis_keyword: str | None = None,
    ) -> None:
        """
        校验高级筛选权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param cat_id: 分类 ID
        :param region: 地区关键字
        :param year_start: 起始年份
        :param year_end: 结束年份
        :param stem_keyword: 题干关键字
        :param option_keyword: 选项关键字
        :param analysis_keyword: 解析关键字
        :return:
        """
        need_verify = (
            cat_id is not None
            or year_start is not None
            or year_end is not None
            or cls._has_text_value(region)
            or cls._has_text_value(stem_keyword)
            or cls._has_text_value(option_keyword)
            or cls._has_text_value(analysis_keyword)
        )
        if not need_verify:
            return

        await cls._require_entitlement(
            db=db,
            user_id=user_id,
            entitlement_code=cls.QBANK_FILTER_ENTITLEMENT_CODE,
            message='当前筛选条件需要会员权限',
        )

    @classmethod
    async def verify_knowledge_access(
        cls,
        *,
        db: AsyncSession,
        user_id: int,
        knowledge_point: list[Any] | None = None,
        knowledge_ids: list[int] | None = None,
        knowledge_names: list[str] | None = None,
    ) -> None:
        """
        校验知识点访问权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param knowledge_point: 知识点对象列表
        :param knowledge_ids: 知识点 ID 列表
        :param knowledge_names: 知识点名称列表
        :return:
        """
        need_verify = (
            cls._has_iterable_value(knowledge_point)
            or cls._has_iterable_value(knowledge_ids)
            or cls._has_iterable_value(knowledge_names)
        )
        if not need_verify:
            return

        await cls._require_entitlement(
            db=db,
            user_id=user_id,
            entitlement_code=cls.KNOWLEDGE_ACCESS_ENTITLEMENT_CODE,
            message='按知识点刷题需要会员权限',
        )

    @staticmethod
    async def verify_session_access(*, db: AsyncSession, user_id: int, session_id: int) -> None:
        """
        校验会话访问权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 会话 ID
        :return:
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')

    @staticmethod
    async def verify_scene_access(*, db: AsyncSession, user_id: int, scene_mask: int) -> None:
        """
        预留场景权限校验

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param scene_mask: 场景位掩码
        :return:
        """
        return None


membership_service = MembershipService()
