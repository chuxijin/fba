#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.study_plan.model.ability_profile import (
    StudyAbilityAttempt,
    StudyAbilityAttemptCategory,
    StudyAbilityCatalog,
    StudyAbilityCategoryBinding,
    StudyUserCategoryProfile,
)


class CRUDStudyAbilityCatalog(CRUDPlus[StudyAbilityCatalog]):
    """能力练习目录数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> StudyAbilityCatalog | None:
        """
        获取能力目录项

        :param db: 数据库会话
        :param pk: 目录 ID
        :return:
        """
        return await self.select_model(db, pk, deleted=0)

    async def get_by_key(
        self, db: AsyncSession, ability_key: str, domain: str = 'civil_service',
    ) -> StudyAbilityCatalog | None:
        """
        按业务领域和能力标识获取目录项

        :param db: 数据库会话
        :param ability_key: 能力标识
        :param domain: 业务领域
        :return:
        """
        return await self.select_model_by_column(db, domain=domain, ability_key=ability_key, deleted=0)

    async def list_catalog(
        self,
        db: AsyncSession,
        domain: str | None = None,
        keyword: str | None = None,
        include_inactive: bool = True,
    ) -> Sequence[StudyAbilityCatalog]:
        """
        获取能力目录列表

        :param db: 数据库会话
        :param domain: 业务领域
        :param keyword: 搜索关键词
        :param include_inactive: 是否包含停用项
        :return:
        """
        filters = [StudyAbilityCatalog.deleted == 0]
        if domain:
            filters.append(StudyAbilityCatalog.domain == domain)
        if keyword:
            keyword_pattern = f'%{keyword}%'
            filters.append(
                or_(
                    StudyAbilityCatalog.ability_key.like(keyword_pattern),
                    StudyAbilityCatalog.title.like(keyword_pattern),
                    StudyAbilityCatalog.category.like(keyword_pattern),
                )
            )
        if not include_inactive:
            filters.append(StudyAbilityCatalog.is_active.is_(True))

        stmt = (
            select(StudyAbilityCatalog)
            .where(*filters)
            .order_by(
                StudyAbilityCatalog.domain.asc(),
                StudyAbilityCatalog.category.asc(),
                StudyAbilityCatalog.title.asc(),
                StudyAbilityCatalog.id.asc(),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().all()


class CRUDStudyAbilityCategoryBinding(CRUDPlus[StudyAbilityCategoryBinding]):
    """能力练习分类绑定数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> StudyAbilityCategoryBinding | None:
        """
        获取能力分类绑定

        :param db: 数据库会话
        :param pk: 绑定 ID
        :return:
        """
        return await self.select_model(db, pk, deleted=0)

    async def list_by_ability_mode(
        self, db: AsyncSession, ability_key: str, mode: str | None,
    ) -> Sequence[StudyAbilityCategoryBinding]:
        """
        获取能力练习绑定的分类节点

        :param db: 数据库会话
        :param ability_key: 能力标识
        :param mode: 练习模式
        :return:
        """
        filters = [
            StudyAbilityCategoryBinding.ability_key == ability_key,
            StudyAbilityCategoryBinding.deleted == 0,
        ]
        if mode:
            filters.append(or_(StudyAbilityCategoryBinding.mode == mode, StudyAbilityCategoryBinding.mode.is_(None)))
        else:
            filters.append(StudyAbilityCategoryBinding.mode.is_(None))

        stmt = (
            select(StudyAbilityCategoryBinding)
            .where(*filters)
            .order_by(StudyAbilityCategoryBinding.is_primary.desc(), StudyAbilityCategoryBinding.id.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def list_bindings(
        self,
        db: AsyncSession,
        ability_key: str | None = None,
        category_id: int | None = None,
        role: str | None = None,
    ) -> Sequence[StudyAbilityCategoryBinding]:
        """
        获取能力分类绑定列表

        :param db: 数据库会话
        :param ability_key: 能力标识
        :param category_id: 分类 ID
        :param role: 绑定角色
        :return:
        """
        filters = [StudyAbilityCategoryBinding.deleted == 0]
        if ability_key:
            filters.append(StudyAbilityCategoryBinding.ability_key == ability_key)
        if category_id:
            filters.append(StudyAbilityCategoryBinding.category_id == category_id)
        if role:
            filters.append(StudyAbilityCategoryBinding.role == role)

        stmt = (
            select(StudyAbilityCategoryBinding)
            .where(*filters)
            .order_by(
                StudyAbilityCategoryBinding.ability_key.asc(),
                StudyAbilityCategoryBinding.is_primary.desc(),
                StudyAbilityCategoryBinding.role.asc(),
                StudyAbilityCategoryBinding.id.asc(),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_duplicate(
        self,
        db: AsyncSession,
        ability_key: str,
        mode: str | None,
        category_id: int,
        role: str,
        exclude_id: int | None = None,
    ) -> StudyAbilityCategoryBinding | None:
        """
        获取重复绑定

        :param db: 数据库会话
        :param ability_key: 能力标识
        :param mode: 练习模式
        :param category_id: 分类 ID
        :param role: 绑定角色
        :param exclude_id: 排除绑定 ID
        :return:
        """
        filters = [
            StudyAbilityCategoryBinding.ability_key == ability_key,
            StudyAbilityCategoryBinding.category_id == category_id,
            StudyAbilityCategoryBinding.role == role,
            StudyAbilityCategoryBinding.deleted == 0,
        ]
        if mode:
            filters.append(StudyAbilityCategoryBinding.mode == mode)
        else:
            filters.append(StudyAbilityCategoryBinding.mode.is_(None))
        if exclude_id is not None:
            filters.append(StudyAbilityCategoryBinding.id != exclude_id)

        stmt = select(StudyAbilityCategoryBinding).where(*filters).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


class CRUDStudyAbilityAttempt(CRUDPlus[StudyAbilityAttempt]):
    """能力练习原始记录数据库操作类"""

    async def get_by_client_session(
        self, db: AsyncSession, user_id: int, client_session_id: str,
    ) -> StudyAbilityAttempt | None:
        """
        按客户端会话 ID 获取练习记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param client_session_id: 客户端会话 ID
        :return:
        """
        return await self.select_model_by_column(
            db,
            user_id=user_id,
            client_session_id=client_session_id,
            deleted=0,
        )


class CRUDStudyAbilityAttemptCategory(CRUDPlus[StudyAbilityAttemptCategory]):
    """能力练习分类贡献数据库操作类"""


class CRUDStudyUserCategoryProfile(CRUDPlus[StudyUserCategoryProfile]):
    """用户分类画像数据库操作类"""

    async def get_by_user_category_source(
        self,
        db: AsyncSession,
        user_id: int,
        category_id: int,
        source_type: str,
    ) -> StudyUserCategoryProfile | None:
        """
        获取用户分类画像

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param category_id: 分类 ID
        :param source_type: 来源类型
        :return:
        """
        return await self.select_model_by_column(
            db,
            user_id=user_id,
            category_id=category_id,
            source_type=source_type,
            deleted=0,
        )

    async def list_by_user(
        self, db: AsyncSession, user_id: int, source_type: str | None = None,
    ) -> Sequence[StudyUserCategoryProfile]:
        """
        获取用户分类画像列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param source_type: 来源类型
        :return:
        """
        filters = [StudyUserCategoryProfile.user_id == user_id, StudyUserCategoryProfile.deleted == 0]
        if source_type:
            filters.append(StudyUserCategoryProfile.source_type == source_type)

        stmt = (
            select(StudyUserCategoryProfile)
            .where(*filters)
            .order_by(StudyUserCategoryProfile.weakness_score.desc(), StudyUserCategoryProfile.updated_time.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()


study_ability_catalog_dao = CRUDStudyAbilityCatalog(StudyAbilityCatalog)
study_ability_category_binding_dao = CRUDStudyAbilityCategoryBinding(StudyAbilityCategoryBinding)
study_ability_attempt_dao = CRUDStudyAbilityAttempt(StudyAbilityAttempt)
study_ability_attempt_category_dao = CRUDStudyAbilityAttemptCategory(StudyAbilityAttemptCategory)
study_user_category_profile_dao = CRUDStudyUserCategoryProfile(StudyUserCategoryProfile)
