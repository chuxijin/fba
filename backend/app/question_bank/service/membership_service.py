#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import ResourceType
from backend.app.access.engine.decide import access_decision_engine
from backend.app.access.engine.snapshot import snapshot_service
from backend.app.access.schema.engine import AccessContext
from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.crud.crud_question import question_dao
from backend.app.question_bank.model import QuestionPlacement
from backend.common.exception import errors
from backend.utils.timezone import timezone

_FEATURE_ADVANCED_FILTER = 'qbank.advanced_filter'
_FEATURE_KNOWLEDGE_PRACTICE = 'qbank.knowledge_practice'


class MembershipService:
    """题库权益服务(基于 access 决策引擎)"""

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
    async def _decide_resource(
        *,
        db: AsyncSession,
        user_id: int,
        resource_type: str,
        resource_id: int,
        consume_trial: bool = False,
        deny_message: str = '当前资源需要会员权限',
    ) -> None:
        """
        统一资源决策入口

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param resource_type: 资源类型
        :param resource_id: 资源 ID
        :param consume_trial: 是否允许扣减试看额度
        :param deny_message: 拒绝时提示
        :return:
        """
        ctx = AccessContext(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            consume_trial=consume_trial,
        )
        decision = await access_decision_engine.decide(db, ctx)
        if not decision.allowed:
            raise errors.ForbiddenError(msg=deny_message)

    @staticmethod
    async def _user_has_feature(
        *,
        db: AsyncSession,
        user_id: int,
        entitlement_code: str,
    ) -> bool:
        """
        判断用户是否拥有指定跨域功能权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :return:
        """
        snapshot = await snapshot_service.load(db, user_id=user_id, ts=timezone.now())
        if snapshot.has_subscription_entitlement(entitlement_code):
            return True
        return snapshot.has_direct_grant(entitlement_code)

    @classmethod
    async def verify_bank_access(
        cls,
        *,
        db: AsyncSession,
        user_id: int,
        bank_id: int,
        bank: Any | None = None,
    ) -> None:
        """
        校验用户是否有访问题库的权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        :param bank: 已加载的题库对象, 传入则跳过 DB 查询
        :return:
        """
        if bank is None:
            bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg='刷题内容不存在')
        if bank.owner_id == user_id:
            return

        await cls._decide_resource(
            db=db,
            user_id=user_id,
            resource_type=ResourceType.QBANK,
            resource_id=bank_id,
            consume_trial=False,
            deny_message='当前内容需要会员权限',
        )

    @classmethod
    async def verify_chapter_access(cls, *, db: AsyncSession, user_id: int, chapter_id: int) -> None:
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

        await cls.verify_bank_access(db=db, user_id=user_id, bank_id=chapter.bank_id)

    @classmethod
    async def verify_bank_chapter_relation(
        cls,
        *,
        db: AsyncSession,
        bank_id: int,
        chapter_id: int,
        bank: Any | None = None,
        chapter: Any | None = None,
    ) -> None:
        """
        校验篇章是否属于题库当前篇章来源

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param chapter_id: 篇章 ID
        :param bank: 已加载的题库对象, 传入则跳过 DB 查询
        :param chapter: 已加载的篇章对象, 传入则跳过 DB 查询
        :return:
        """
        if bank is None:
            bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg='刷题内容不存在')

        if chapter is None:
            chapter = await chapter_dao.get(db, chapter_id)
        if not chapter:
            raise errors.NotFoundError(msg='篇章不存在')

        source_bank_id = bank.chapter_source_bank_id or bank.id
        if chapter.bank_id != source_bank_id:
            raise errors.ForbiddenError(msg=f'篇章 ID {chapter_id} 不属于题库 ID {bank_id} 的篇章来源')

    @classmethod
    async def verify_bank_chapter_access(cls, *, db: AsyncSession, user_id: int, bank_id: int, chapter_id: int) -> None:
        """
        校验篇章与题库关系并校验访问权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        :param chapter_id: 篇章 ID
        :return:
        """
        await cls.verify_bank_chapter_relation(db=db, bank_id=bank_id, chapter_id=chapter_id)
        await cls.verify_bank_access(db=db, user_id=user_id, bank_id=bank_id)

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
        :param user_id: 用户 ID, 传入时同步校验
        :return:
        """
        chapter = await chapter_dao.get(db, chapter_id)
        if not chapter:
            raise errors.NotFoundError(msg='篇章不存在')

        if bank_id is not None:
            # Cut A: 一次性加载 bank, 复用给后续 verify_bank_chapter_relation + verify_bank_access
            bank = await bank_dao.get(db, bank_id)
            await cls.verify_bank_chapter_relation(
                db=db,
                bank_id=bank_id,
                chapter_id=chapter_id,
                bank=bank,
                chapter=chapter,
            )
            if user_id is not None:
                await cls.verify_bank_access(
                    db=db,
                    user_id=user_id,
                    bank_id=bank_id,
                    bank=bank,
                )
            return bank_id

        candidate_bank_ids = await cls._get_active_bank_ids_by_chapter_source(db=db, source_bank_id=chapter.bank_id)
        if not candidate_bank_ids:
            raise errors.NotFoundError(msg='篇章关联内容不存在')
        if len(candidate_bank_ids) > 1:
            raise errors.RequestError(msg='当前篇章被多个题库复用, 请传 bank_id 明确题库上下文')

        resolved_bank_id = candidate_bank_ids[0]
        if user_id is not None:
            await cls.verify_bank_access(db=db, user_id=user_id, bank_id=resolved_bank_id)
        return resolved_bank_id

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
        from sqlalchemy import or_

        from backend.app.question_bank.model import QuestionBank

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
    async def verify_question_access(cls, *, db: AsyncSession, user_id: int, question_id: int) -> None:
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

        bank_ids = await cls._get_question_bank_ids(db=db, question_ids=[question_id])
        target_bank_ids = bank_ids.get(question_id, [])
        if not target_bank_ids:
            return

        last_error: errors.ForbiddenError | None = None
        for bank_id in target_bank_ids:
            try:
                await cls.verify_bank_access(db=db, user_id=user_id, bank_id=bank_id)
                return
            except errors.ForbiddenError as exc:
                last_error = exc
                continue

        raise last_error or errors.ForbiddenError(msg='当前题目需要会员权限')

    @classmethod
    async def verify_question_ids_access(cls, *, db: AsyncSession, user_id: int, question_ids: list[int]) -> None:
        """
        批量校验题目访问权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_ids: 题目 ID 列表
        :return:
        """
        normalized_ids = [qid for qid in dict.fromkeys(question_ids) if qid > 0]
        if not normalized_ids:
            return

        bank_map = await cls._get_question_bank_ids(db=db, question_ids=normalized_ids)
        for qid in normalized_ids:
            bank_ids = bank_map.get(qid, [])
            if not bank_ids:
                continue
            await cls.verify_bank_access(db=db, user_id=user_id, bank_id=bank_ids[0])

    @staticmethod
    async def _get_question_bank_ids(
        *,
        db: AsyncSession,
        question_ids: list[int],
    ) -> dict[int, list[int]]:
        """
        获取题目所属题库 ID 映射

        :param db: 数据库会话
        :param question_ids: 题目 ID 列表
        :return:
        """
        if not question_ids:
            return {}

        from backend.app.question_bank.model import QuestionBank

        stmt = (
            select(QuestionPlacement.question_id, QuestionPlacement.bank_id)
            .join(QuestionBank, QuestionBank.id == QuestionPlacement.bank_id)
            .where(
                QuestionPlacement.question_id.in_(question_ids),
                QuestionPlacement.is_active.is_(True),
                QuestionBank.status == 1,
            )
        )
        rows = (await db.execute(stmt)).all()

        result: dict[int, list[int]] = {}
        for question_id, bank_id in rows:
            result.setdefault(question_id, []).append(bank_id)
        return result

    @classmethod
    async def verify_bank_list_access(cls, *, db: AsyncSession, user_id: int, bank_id: int) -> None:
        """
        校验题库题目列表访问权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        :return:
        """
        await cls.verify_bank_access(db=db, user_id=user_id, bank_id=bank_id)

    @classmethod
    async def verify_placement_access(cls, *, db: AsyncSession, user_id: int, placement_id: int) -> None:
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
        placement = (await db.execute(stmt)).scalars().first()
        if not placement:
            raise errors.NotFoundError(msg='题目挂载不存在或已禁用')

        await cls.verify_bank_access(db=db, user_id=user_id, bank_id=placement.bank_id)

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
        :param region: 地区
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

        if await cls._user_has_feature(db=db, user_id=user_id, entitlement_code=_FEATURE_ADVANCED_FILTER):
            return
        raise errors.ForbiddenError(msg='当前筛选条件需要会员权限')

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

        if await cls._user_has_feature(db=db, user_id=user_id, entitlement_code=_FEATURE_KNOWLEDGE_PRACTICE):
            return
        raise errors.ForbiddenError(msg='按知识点刷题需要会员权限')

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
        """预留场景权限校验"""
        return None


membership_service = MembershipService()
