#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_generation.crud import candidate_dao, material_dao, task_dao
from backend.app.question_generation.model import (
    QuestionGenerationCandidate,
    QuestionGenerationMaterial,
    QuestionGenerationTask,
)
from backend.app.question_generation.schema import (
    CandidateReviewParam,
    CreateMaterialParam,
    DeleteCandidateParam,
    DeleteMaterialParam,
    DeleteTaskParam,
    MaterialQueryParam,
    StartGenerationParam,
    StartGenerationResult,
    UpdateMaterialParam,
)
from backend.common.exception import errors


class QuestionGenerationService:
    """AI 出题服务"""

    @staticmethod
    async def get_material(*, db: AsyncSession, pk: int) -> QuestionGenerationMaterial:
        """
        获取素材详情

        :param db: 数据库会话
        :param pk: 素材 ID
        :return:
        """
        material = await material_dao.get(db, pk)
        if material is None:
            raise errors.NotFoundError(msg='出题素材不存在')
        return material

    @staticmethod
    async def get_material_list(
        *,
        db: AsyncSession,
        params: MaterialQueryParam,
    ) -> Sequence[QuestionGenerationMaterial]:
        """
        获取素材列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        return await material_dao.get_list(db, params)

    @staticmethod
    async def create_material(
        *,
        db: AsyncSession,
        obj: CreateMaterialParam,
        created_by: int,
    ) -> QuestionGenerationMaterial:
        """
        创建素材

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者
        :return:
        """
        return await material_dao.create(db, obj, created_by=created_by)

    @staticmethod
    async def update_material(
        *,
        db: AsyncSession,
        pk: int,
        obj: UpdateMaterialParam,
        updated_by: int,
    ) -> int:
        """
        更新素材

        :param db: 数据库会话
        :param pk: 素材 ID
        :param obj: 更新参数
        :param updated_by: 更新者
        :return:
        """
        material = await material_dao.get(db, pk)
        if material is None:
            raise errors.NotFoundError(msg='出题素材不存在')
        return await material_dao.update(db, pk, obj, updated_by=updated_by)

    @staticmethod
    async def delete_material(*, db: AsyncSession, obj: DeleteMaterialParam) -> int:
        """
        删除素材

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await material_dao.delete(db, obj.ids)

    @staticmethod
    async def start_generation(
        *,
        db: AsyncSession,
        params: StartGenerationParam,
        created_by: int,
    ) -> StartGenerationResult:
        """
        创建出题任务

        :param db: 数据库会话
        :param params: 启动参数
        :param created_by: 创建者
        :return:
        """
        material = await material_dao.get(db, params.material_id)
        if material is None:
            raise errors.NotFoundError(msg='出题素材不存在')

        automatic_params = params.model_copy(
            update={
                'target_question_types': None,
                'question_count': 1,
            }
        )

        task = await task_dao.create(db, automatic_params, created_by=created_by)
        await db.commit()

        from backend.app.task.tasks.question_generation.tasks import run_question_generation_task

        run_question_generation_task.delay(task.id)
        return StartGenerationResult(task_id=task.id, status='pending')

    @staticmethod
    async def get_task(*, db: AsyncSession, pk: int) -> QuestionGenerationTask:
        """
        获取任务详情

        :param db: 数据库会话
        :param pk: 任务 ID
        :return:
        """
        task = await task_dao.get(db, pk)
        if task is None:
            raise errors.NotFoundError(msg='出题任务不存在')
        return task

    @staticmethod
    async def get_task_list(
        *,
        db: AsyncSession,
        material_id: int | None = None,
        status: str | None = None,
    ) -> Sequence[QuestionGenerationTask]:
        """
        获取任务列表

        :param db: 数据库会话
        :param material_id: 素材 ID
        :param status: 任务状态
        :return:
        """
        return await task_dao.get_list(db, material_id=material_id, status=status)

    @staticmethod
    async def delete_task(*, db: AsyncSession, obj: DeleteTaskParam) -> int:
        """
        删除出题任务

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await task_dao.delete(db, obj.ids)

    @staticmethod
    async def get_candidate(*, db: AsyncSession, pk: int) -> QuestionGenerationCandidate:
        """
        获取候选题详情

        :param db: 数据库会话
        :param pk: 候选题 ID
        :return:
        """
        candidate = await candidate_dao.get(db, pk)
        if candidate is None:
            raise errors.NotFoundError(msg='候选题不存在')
        return candidate

    @staticmethod
    async def get_candidate_list(
        *,
        db: AsyncSession,
        task_id: int | None = None,
        material_id: int | None = None,
        status: str | None = None,
    ) -> Sequence[QuestionGenerationCandidate]:
        """
        获取候选题列表

        :param db: 数据库会话
        :param task_id: 任务 ID
        :param material_id: 素材 ID
        :param status: 候选题状态
        :return:
        """
        return await candidate_dao.get_list(db, task_id=task_id, material_id=material_id, status=status)

    @staticmethod
    async def delete_candidate(*, db: AsyncSession, obj: DeleteCandidateParam) -> int:
        """
        删除候选题

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await candidate_dao.delete(db, obj.ids)

    @staticmethod
    async def review_candidate(
        *,
        db: AsyncSession,
        pk: int,
        obj: CandidateReviewParam,
        updated_by: int,
    ) -> None:
        """
        审核候选题

        :param db: 数据库会话
        :param pk: 候选题 ID
        :param obj: 审核参数
        :param updated_by: 更新者
        :return:
        """
        candidate = await candidate_dao.get(db, pk)
        if candidate is None:
            raise errors.NotFoundError(msg='候选题不存在')

        qc_result: dict[str, Any] | None = None
        if obj.reason:
            qc_result = dict(candidate.qc_result or {})
            qc_result['review_reason'] = obj.reason
        await candidate_dao.update_status(
            db,
            candidate,
            status=obj.status,
            updated_by=updated_by,
            qc_result=qc_result,
        )


question_generation_service: QuestionGenerationService = QuestionGenerationService()
