#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.study_plan.model.mentor import StudyMentorStudent


class CRUDStudyMentorStudent(CRUDPlus[StudyMentorStudent]):
    """导师学员关联数据库操作类"""

    async def get(self, db: AsyncSession, relation_id: int) -> StudyMentorStudent | None:
        """
        获取关系详情

        :param db: 数据库会话
        :param relation_id: 关系 ID
        :return:
        """
        return await self.select_model(db, relation_id, deleted=0)

    async def get_pair(
        self, db: AsyncSession, mentor_id: int, student_id: int,
    ) -> StudyMentorStudent | None:
        """
        获取指定导师与学员的关系

        :param db: 数据库会话
        :param mentor_id: 导师用户 ID
        :param student_id: 学员用户 ID
        :return:
        """
        return await self.select_model_by_column(
            db, mentor_id=mentor_id, student_id=student_id, deleted=0,
        )

    async def list_students_of_mentor(
        self, db: AsyncSession, mentor_id: int,
    ) -> Sequence[StudyMentorStudent]:
        """
        获取导师名下所有生效学员

        :param db: 数据库会话
        :param mentor_id: 导师用户 ID
        :return:
        """
        stmt = (
            select(StudyMentorStudent)
            .where(
                StudyMentorStudent.mentor_id == mentor_id,
                StudyMentorStudent.status == 'active',
                StudyMentorStudent.deleted == 0,
            )
            .order_by(StudyMentorStudent.assigned_at.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def list_mentors_of_student(
        self, db: AsyncSession, student_id: int,
    ) -> Sequence[StudyMentorStudent]:
        """
        获取学员的所有生效导师

        :param db: 数据库会话
        :param student_id: 学员用户 ID
        :return:
        """
        stmt = (
            select(StudyMentorStudent)
            .where(
                StudyMentorStudent.student_id == student_id,
                StudyMentorStudent.status == 'active',
                StudyMentorStudent.deleted == 0,
            )
            .order_by(StudyMentorStudent.assigned_at.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()


study_mentor_student_dao = CRUDStudyMentorStudent(StudyMentorStudent)
