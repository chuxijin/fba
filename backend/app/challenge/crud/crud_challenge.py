#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import sqlalchemy as sa

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.challenge.model import (
    ChallengeAttempt,
    ChallengeLevel,
    ChallengeLevelSection,
    UserChallengeProgress,
)
from backend.app.question_bank.model import (
    MaterialAnchor,
    Question,
    QuestionAnalysis,
    QuestionInteractionAnnotation,
    QuestionMaterial,
    QuestionPlacement,
)


class CRUDChallengeLevel(CRUDPlus[ChallengeLevel]):
    """闯关关卡数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> ChallengeLevel | None:
        """
        获取关卡

        :param db: 数据库会话
        :param pk: 关卡 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_with_sections(self, db: AsyncSession, pk: int) -> ChallengeLevel | None:
        """
        获取关卡及题目分组

        :param db: 数据库会话
        :param pk: 关卡 ID
        :return:
        """
        stmt = (
            select(ChallengeLevel)
            .where(ChallengeLevel.id == pk, ChallengeLevel.deleted == 0)
            .options(selectinload(ChallengeLevel.sections))
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_identity(
        self,
        db: AsyncSession,
        challenge_key: str,
        stage: str,
        level_no: int,
    ) -> ChallengeLevel | None:
        """
        按闯关标识和关卡序号获取关卡

        :param db: 数据库会话
        :param challenge_key: 闯关标识
        :param stage: 难度阶段
        :param level_no: 阶段内关卡号
        :return:
        """
        stmt = select(ChallengeLevel).where(
            ChallengeLevel.challenge_key == challenge_key,
            ChallengeLevel.stage == stage,
            ChallengeLevel.level_no == level_no,
            ChallengeLevel.deleted == 0,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_global_no(
        self,
        db: AsyncSession,
        challenge_key: str,
        global_no: int,
    ) -> ChallengeLevel | None:
        """
        按全局序号获取关卡

        :param db: 数据库会话
        :param challenge_key: 闯关标识
        :param global_no: 全局序号
        :return:
        """
        stmt = select(ChallengeLevel).where(
            ChallengeLevel.challenge_key == challenge_key,
            ChallengeLevel.global_no == global_no,
            ChallengeLevel.deleted == 0,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_all(
        self,
        db: AsyncSession,
        challenge_key: str | None = None,
        status: str | None = None,
    ) -> list[ChallengeLevel]:
        """
        获取关卡列表

        :param db: 数据库会话
        :param challenge_key: 闯关标识
        :param status: 关卡状态
        :return:
        """
        stmt = (
            select(ChallengeLevel)
            .where(ChallengeLevel.deleted == 0)
            .options(selectinload(ChallengeLevel.sections))
            .order_by(ChallengeLevel.sort_order, ChallengeLevel.global_no)
        )
        if challenge_key:
            stmt = stmt.where(ChallengeLevel.challenge_key == challenge_key)
        if status:
            stmt = stmt.where(ChallengeLevel.status == status)
        result = await db.execute(stmt)
        return list(result.scalars().unique().all())

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> ChallengeLevel:
        """
        创建关卡

        :param db: 数据库会话
        :param data: 关卡数据
        :return:
        """
        level = ChallengeLevel(**data)
        db.add(level)
        await db.flush()
        await db.refresh(level)
        return level

    async def update(self, db: AsyncSession, pk: int, data: dict[str, Any]) -> int:
        """
        更新关卡

        :param db: 数据库会话
        :param pk: 关卡 ID
        :param data: 更新数据
        :return:
        """
        return await self.update_model(db, pk, data)

    async def replace_sections(
        self,
        db: AsyncSession,
        level_id: int,
        sections: list[dict[str, Any]],
    ) -> None:
        """
        替换关卡题目分组

        :param db: 数据库会话
        :param level_id: 关卡 ID
        :param sections: 分组数据
        :return:
        """
        await db.execute(sa.delete(ChallengeLevelSection).where(ChallengeLevelSection.level_id == level_id))
        db.add_all([ChallengeLevelSection(level_id=level_id, **item) for item in sections])
        await db.flush()


class CRUDChallengeAttempt(CRUDPlus[ChallengeAttempt]):
    """闯关挑战数据库操作类"""

    async def get_by_key(
        self,
        db: AsyncSession,
        attempt_key: str,
        *,
        for_update: bool = False,
    ) -> ChallengeAttempt | None:
        """
        按挑战标识获取记录

        :param db: 数据库会话
        :param attempt_key: 挑战标识
        :param for_update: 是否加行锁
        :return:
        """
        stmt = select(ChallengeAttempt).where(
            ChallengeAttempt.attempt_key == attempt_key,
            ChallengeAttempt.deleted == 0,
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_in_progress(
        self,
        db: AsyncSession,
        user_id: int,
        level_id: int,
    ) -> ChallengeAttempt | None:
        """
        获取进行中的挑战

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param level_id: 关卡 ID
        :return:
        """
        stmt = (
            select(ChallengeAttempt)
            .where(
                ChallengeAttempt.user_id == user_id,
                ChallengeAttempt.level_id == level_id,
                ChallengeAttempt.status == 'in_progress',
                ChallengeAttempt.deleted == 0,
            )
            .order_by(ChallengeAttempt.started_at.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> ChallengeAttempt:
        """
        创建挑战记录

        :param db: 数据库会话
        :param data: 挑战数据
        :return:
        """
        attempt = ChallengeAttempt(**data)
        db.add(attempt)
        await db.flush()
        await db.refresh(attempt)
        return attempt

    async def update(self, db: AsyncSession, pk: int, data: dict[str, Any]) -> int:
        """
        更新挑战记录

        :param db: 数据库会话
        :param pk: 挑战记录 ID
        :param data: 更新数据
        :return:
        """
        return await self.update_model(db, pk, data)

    async def get_recent_completed(
        self,
        db: AsyncSession,
        user_id: int,
        level_id: int,
        limit: int,
    ) -> list[ChallengeAttempt]:
        """
        获取最近完成的挑战记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param level_id: 关卡 ID
        :param limit: 获取数量
        :return:
        """
        if limit <= 0:
            return []
        stmt = (
            select(ChallengeAttempt)
            .where(
                ChallengeAttempt.user_id == user_id,
                ChallengeAttempt.level_id == level_id,
                ChallengeAttempt.status == 'completed',
                ChallengeAttempt.deleted == 0,
            )
            .order_by(ChallengeAttempt.completed_at.desc(), ChallengeAttempt.id.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


class CRUDUserChallengeProgress(CRUDPlus[UserChallengeProgress]):
    """用户闯关进度数据库操作类"""

    async def get_by_level(
        self,
        db: AsyncSession,
        user_id: int,
        level_id: int,
        *,
        for_update: bool = False,
    ) -> UserChallengeProgress | None:
        """
        获取用户关卡进度

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param level_id: 关卡 ID
        :param for_update: 是否加行锁
        :return:
        """
        stmt = select(UserChallengeProgress).where(
            UserChallengeProgress.user_id == user_id,
            UserChallengeProgress.level_id == level_id,
            UserChallengeProgress.deleted == 0,
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_levels(
        self,
        db: AsyncSession,
        user_id: int,
        level_ids: list[int],
    ) -> dict[int, UserChallengeProgress]:
        """
        批量获取用户关卡进度

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param level_ids: 关卡 ID 列表
        :return:
        """
        if not level_ids:
            return {}
        stmt = select(UserChallengeProgress).where(
            UserChallengeProgress.user_id == user_id,
            UserChallengeProgress.level_id.in_(level_ids),
            UserChallengeProgress.deleted == 0,
        )
        result = await db.execute(stmt)
        return {item.level_id: item for item in result.scalars().all()}

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> UserChallengeProgress:
        """
        创建用户关卡进度

        :param db: 数据库会话
        :param data: 进度数据
        :return:
        """
        progress = UserChallengeProgress(**data)
        db.add(progress)
        await db.flush()
        await db.refresh(progress)
        return progress

    async def update(self, db: AsyncSession, pk: int, data: dict[str, Any]) -> int:
        """
        更新用户关卡进度

        :param db: 数据库会话
        :param pk: 进度 ID
        :param data: 更新数据
        :return:
        """
        return await self.update_model(db, pk, data)


class CRUDChallengeQuestionSource:
    """闯关题源数据库操作类"""

    @staticmethod
    async def get_random_annotation_by_anchor_role(
        *,
        db: AsyncSession,
        role: str,
        bank_id: int | None = None,
        material_ids: list[int] | None = None,
        exclude_annotation_ids: list[int] | None = None,
    ) -> tuple[QuestionInteractionAnnotation, QuestionMaterial] | None:
        """
        按题目标注中的锚点角色随机抽取题目材料

        :param db: 数据库会话
        :param role: 锚点语义角色
        :param bank_id: 题库 ID
        :param material_ids: 材料 ID 列表
        :param exclude_annotation_ids: 排除标注 ID
        :return:
        """
        stmt = (
            select(QuestionInteractionAnnotation, QuestionMaterial)
            .join(QuestionMaterial, QuestionMaterial.id == QuestionInteractionAnnotation.material_id)
            .where(
                QuestionInteractionAnnotation.interaction_type == 'anchorLocate',
                QuestionInteractionAnnotation.status == 10,
                QuestionInteractionAnnotation.deleted == 0,
                QuestionInteractionAnnotation.material_id.is_not(None),
                QuestionMaterial.is_active.is_(True),
                QuestionMaterial.deleted == 0,
            )
        )
        if bank_id is not None:
            stmt = stmt.where(QuestionMaterial.bank_id == bank_id)
        if material_ids:
            stmt = stmt.where(QuestionInteractionAnnotation.material_id.in_(material_ids))
        if exclude_annotation_ids:
            stmt = stmt.where(QuestionInteractionAnnotation.id.not_in(exclude_annotation_ids))

        result = await db.execute(stmt.order_by(sa.func.random()))
        for annotation, material in result.all():
            config = annotation.config if isinstance(annotation.config, dict) else {}
            anchor_roles = config.get('anchor_roles')
            if not isinstance(anchor_roles, dict):
                continue
            if any(str(item).strip() == role for item in anchor_roles.values()):
                return annotation, material
        return None

    @staticmethod
    async def get_material_anchor_candidates(
        *,
        db: AsyncSession,
        material_id: int,
        roles: list[str],
    ) -> Sequence[MaterialAnchor]:
        """
        获取材料内可用候选锚点

        :param db: 数据库会话
        :param material_id: 材料 ID
        :param roles: 锚点语义角色列表
        :return:
        """
        stmt = select(MaterialAnchor).where(
            MaterialAnchor.material_id == material_id,
            MaterialAnchor.status == 10,
            MaterialAnchor.deleted == 0,
        )
        if roles:
            stmt = stmt.where(MaterialAnchor.role.in_(roles))

        stmt = stmt.order_by(MaterialAnchor.id.asc())
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_pool_questions(
        *,
        db: AsyncSession,
        count: int,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        question_types: list[str] | None = None,
        difficulty_min: Decimal | None = None,
        difficulty_max: Decimal | None = None,
        knowledge_points: list[str] | None = None,
        exclude_ids: list[int] | None = None,
    ) -> Sequence[Question]:
        """
        按规则随机抽取题库题目

        :param db: 数据库会话
        :param count: 抽题数量
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param question_types: 题型列表
        :param difficulty_min: 最低难度
        :param difficulty_max: 最高难度
        :param knowledge_points: 知识点列表
        :param exclude_ids: 排除题目 ID
        :return:
        """
        stmt = (
            select(Question)
            .where(Question.content_status == 10, Question.deleted == 0)
            .options(
                selectinload(Question.analyses),
                selectinload(Question.materials),
                selectinload(Question.placements),
            )
        )
        if bank_id is not None or chapter_id is not None:
            stmt = stmt.join(QuestionPlacement, QuestionPlacement.question_id == Question.id).where(
                QuestionPlacement.is_active.is_(True),
                QuestionPlacement.review_status == 10,
                QuestionPlacement.deleted == 0,
            )
        if bank_id is not None:
            stmt = stmt.where(QuestionPlacement.bank_id == bank_id)
        if chapter_id is not None:
            stmt = stmt.where(QuestionPlacement.chapter_id == chapter_id)
        if question_types:
            stmt = stmt.where(Question.type.in_(question_types))
        if difficulty_min is not None:
            stmt = stmt.where(Question.difficulty >= difficulty_min)
        if difficulty_max is not None:
            stmt = stmt.where(Question.difficulty <= difficulty_max)
        if knowledge_points:
            knowledge_conditions = [Question.knowledge_point.contains([item]) for item in knowledge_points]
            stmt = stmt.where(sa.or_(*knowledge_conditions))
        if exclude_ids:
            stmt = stmt.where(Question.id.not_in(exclude_ids))

        stmt = stmt.order_by(sa.func.random()).limit(count)
        result = await db.execute(stmt)
        return result.unique().scalars().all()


challenge_level_dao = CRUDChallengeLevel(ChallengeLevel)
challenge_attempt_dao = CRUDChallengeAttempt(ChallengeAttempt)
user_challenge_progress_dao = CRUDUserChallengeProgress(UserChallengeProgress)
challenge_question_source_dao = CRUDChallengeQuestionSource()
