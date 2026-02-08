#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model.user_profile import (
    GkUserCertificate,
    GkUserEducation,
    GkUserHonor,
    GkUserProfile,
    GkUserRegionPreference,
    GkUserWorkExperience,
)
from backend.app.gongkao.schema.user_profile import (
    CreateUserCertificateParam,
    CreateUserEducationParam,
    CreateUserHonorParam,
    CreateUserProfileParam,
    CreateUserRegionPreferenceParam,
    CreateUserWorkExperienceParam,
    UpdateUserProfileParam,
)


class CRUDUserProfile(CRUDPlus[GkUserProfile]):
    """用户画像数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkUserProfile | None:
        """
        获取用户画像详情（含所有子表）

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.id == pk)
            .options(
                selectinload(self.model.educations),
                selectinload(self.model.region_preferences),
                selectinload(self.model.certificates),
                selectinload(self.model.work_experiences),
                selectinload(self.model.honors),
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, db: AsyncSession, user_id: int) -> GkUserProfile | None:
        """
        通过用户 ID 获取画像（含所有子表）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.user_id == user_id)
            .options(
                selectinload(self.model.educations),
                selectinload(self.model.region_preferences),
                selectinload(self.model.certificates),
                selectinload(self.model.work_experiences),
                selectinload(self.model.honors),
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_select(self, user_id: int | None = None) -> Select:
        """
        获取用户画像列表查询表达式

        :param user_id: 用户 ID
        :return:
        """
        filters = {}
        if user_id is not None:
            filters['user_id'] = user_id
        return await self.select_order('id', 'desc', **filters)

    async def create(self, db: AsyncSession, user_id: int, obj: CreateUserProfileParam) -> GkUserProfile:
        """
        创建用户画像（含所有子表）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 创建参数
        :return:
        """
        # 创建主表
        profile_data = obj.model_dump(exclude={'educations', 'region_preferences', 'certificates', 'work_experiences', 'honors'})
        profile = GkUserProfile(**profile_data, user_id=user_id)
        db.add(profile)
        await db.flush()

        # 创建子表数据
        await self._create_sub_tables(db, profile.id, obj)

        await db.refresh(profile)
        return profile

    async def _create_sub_tables(self, db: AsyncSession, profile_id: int, obj: CreateUserProfileParam) -> None:
        """
        创建子表数据

        :param db: 数据库会话
        :param profile_id: 画像 ID
        :param obj: 创建参数
        :return:
        """
        # 教育经历
        for edu in obj.educations:
            education = GkUserEducation(**edu.model_dump(), profile_id=profile_id)
            db.add(education)

        # 地区偏好
        for pref in obj.region_preferences:
            preference = GkUserRegionPreference(**pref.model_dump(), profile_id=profile_id)
            db.add(preference)

        # 资格证书
        for cert in obj.certificates:
            certificate = GkUserCertificate(**cert.model_dump(), profile_id=profile_id)
            db.add(certificate)

        # 工作经历
        for work in obj.work_experiences:
            experience = GkUserWorkExperience(**work.model_dump(), profile_id=profile_id)
            db.add(experience)

        # 荣誉成就
        for honor in obj.honors:
            honor_obj = GkUserHonor(**honor.model_dump(), profile_id=profile_id)
            db.add(honor_obj)

        await db.flush()

    async def update(self, db: AsyncSession, pk: int, obj: UpdateUserProfileParam) -> int:
        """
        更新用户画像

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        # 更新主表字段（排除子表列表数据）
        from backend.app.gongkao.schema.user_profile import UpdateUserProfileMainParam
        
        main_data = obj.model_dump(
            exclude={'educations', 'region_preferences', 'certificates', 'work_experiences', 'honors'},
            exclude_none=True,
        )
        count = 0
        if main_data:
            # 创建只包含主表字段的更新对象
            main_obj = UpdateUserProfileMainParam(**main_data)
            count = await self.update_model(db, pk, main_obj)

        # 如果提供了子表数据，则替换
        if obj.educations is not None:
            await self._replace_educations(db, pk, obj.educations)
        if obj.region_preferences is not None:
            await self._replace_region_preferences(db, pk, obj.region_preferences)
        if obj.certificates is not None:
            await self._replace_certificates(db, pk, obj.certificates)
        if obj.work_experiences is not None:
            await self._replace_work_experiences(db, pk, obj.work_experiences)
        if obj.honors is not None:
            await self._replace_honors(db, pk, obj.honors)

        return count

    async def _replace_educations(
        self,
        db: AsyncSession,
        profile_id: int,
        educations: list[CreateUserEducationParam],
    ) -> None:
        """替换教育经历"""
        # 删除旧数据
        from sqlalchemy import delete
        await db.execute(delete(GkUserEducation).where(GkUserEducation.profile_id == profile_id))
        # 创建新数据
        for edu in educations:
            education = GkUserEducation(**edu.model_dump(), profile_id=profile_id)
            db.add(education)
        await db.flush()

    async def _replace_region_preferences(
        self,
        db: AsyncSession,
        profile_id: int,
        preferences: list[CreateUserRegionPreferenceParam],
    ) -> None:
        """替换地区偏好"""
        from sqlalchemy import delete
        await db.execute(delete(GkUserRegionPreference).where(GkUserRegionPreference.profile_id == profile_id))
        for pref in preferences:
            preference = GkUserRegionPreference(**pref.model_dump(), profile_id=profile_id)
            db.add(preference)
        await db.flush()

    async def _replace_certificates(
        self,
        db: AsyncSession,
        profile_id: int,
        certificates: list[CreateUserCertificateParam],
    ) -> None:
        """替换资格证书"""
        from sqlalchemy import delete
        await db.execute(delete(GkUserCertificate).where(GkUserCertificate.profile_id == profile_id))
        for cert in certificates:
            certificate = GkUserCertificate(**cert.model_dump(), profile_id=profile_id)
            db.add(certificate)
        await db.flush()

    async def _replace_work_experiences(
        self,
        db: AsyncSession,
        profile_id: int,
        experiences: list[CreateUserWorkExperienceParam],
    ) -> None:
        """替换工作经历"""
        from sqlalchemy import delete
        await db.execute(delete(GkUserWorkExperience).where(GkUserWorkExperience.profile_id == profile_id))
        for work in experiences:
            experience = GkUserWorkExperience(**work.model_dump(), profile_id=profile_id)
            db.add(experience)
        await db.flush()

    async def _replace_honors(
        self,
        db: AsyncSession,
        profile_id: int,
        honors: list[CreateUserHonorParam],
    ) -> None:
        """替换荣誉成就"""
        from sqlalchemy import delete
        await db.execute(delete(GkUserHonor).where(GkUserHonor.profile_id == profile_id))
        for honor in honors:
            honor_obj = GkUserHonor(**honor.model_dump(), profile_id=profile_id)
            db.add(honor_obj)
        await db.flush()

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除用户画像（级联删除子表）

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def delete_by_user_id(self, db: AsyncSession, user_id: int) -> int:
        """
        通过用户 ID 删除画像

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.delete_model_by_column(db, user_id=user_id)


user_profile_dao: CRUDUserProfile = CRUDUserProfile(GkUserProfile)
