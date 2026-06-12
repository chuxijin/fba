#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import sqlalchemy as sa

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_generation.model import (
    QuestionGenerationCandidate,
    QuestionGenerationMaterial,
    QuestionGenerationTask,
)
from backend.app.question_generation.schema import (
    CreateMaterialParam,
    MaterialQueryParam,
    StartGenerationParam,
    UpdateMaterialParam,
)
from backend.utils.timezone import timezone


class CRUDQuestionGenerationMaterial(CRUDPlus[QuestionGenerationMaterial]):
    """AI 出题素材 CRUD"""

    async def get(self, db: AsyncSession, pk: int) -> QuestionGenerationMaterial | None:
        """
        获取素材

        :param db: 数据库会话
        :param pk: 素材 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_list(
        self,
        db: AsyncSession,
        params: MaterialQueryParam,
    ) -> Sequence[QuestionGenerationMaterial]:
        """
        获取素材列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        stmt = sa.select(self.model)
        if params.exam:
            stmt = stmt.where(self.model.exam == params.exam)
        if params.subject:
            stmt = stmt.where(self.model.subject == params.subject)
        if params.section:
            stmt = stmt.where(self.model.section == params.section)
        if params.status:
            stmt = stmt.where(self.model.status == params.status)
        if params.keyword:
            keyword = f'%{params.keyword}%'
            stmt = stmt.where(
                sa.or_(
                    self.model.title.ilike(keyword),
                    self.model.content.ilike(keyword),
                    self.model.source.ilike(keyword),
                )
            )
        stmt = stmt.order_by(self.model.id.desc())
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(
        self,
        db: AsyncSession,
        obj: CreateMaterialParam,
        *,
        created_by: int,
    ) -> QuestionGenerationMaterial:
        """
        创建素材

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者
        :return:
        """
        data = obj.model_dump()
        data['created_by'] = created_by
        material = self.model(**data)
        db.add(material)
        await db.flush()
        return material

    async def update(
        self,
        db: AsyncSession,
        pk: int,
        obj: UpdateMaterialParam,
        *,
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
        data = obj.model_dump()
        data['updated_by'] = updated_by
        return await self.update_model_by_column(db, data, id=pk)

    async def set_process_result(
        self,
        db: AsyncSession,
        material: QuestionGenerationMaterial,
        *,
        status: str,
        process_result: dict[str, Any],
    ) -> None:
        """
        设置素材处理结果

        :param db: 数据库会话
        :param material: 素材
        :param status: 状态
        :param process_result: 处理结果
        :return:
        """
        material.status = status
        material.process_result = process_result
        material.processed_time = timezone.now()
        await db.flush()

    async def delete(self, db: AsyncSession, ids: list[int]) -> int:
        """
        删除素材

        :param db: 数据库会话
        :param ids: 素材 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=ids)


class CRUDQuestionGenerationTask(CRUDPlus[QuestionGenerationTask]):
    """AI 出题任务 CRUD"""

    async def get(self, db: AsyncSession, pk: int) -> QuestionGenerationTask | None:
        """
        获取任务

        :param db: 数据库会话
        :param pk: 任务 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_list(
        self,
        db: AsyncSession,
        *,
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
        stmt = sa.select(self.model)
        if material_id is not None:
            stmt = stmt.where(self.model.material_id == material_id)
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        stmt = stmt.order_by(self.model.id.desc())
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(
        self,
        db: AsyncSession,
        params: StartGenerationParam,
        *,
        created_by: int,
    ) -> QuestionGenerationTask:
        """
        创建任务

        :param db: 数据库会话
        :param params: 启动参数
        :param created_by: 创建者
        :return:
        """
        data = params.model_dump(mode='json')
        task = self.model(
            material_id=params.material_id,
            user_id=params.user_id,
            provider_id=params.provider_id,
            model_id=params.model_id,
            mini_model_id=params.mini_model_id,
            exam=params.exam,
            subject=params.subject,
            section=params.section,
            target_question_types=params.target_question_types,
            question_count=params.question_count,
            input_payload=data,
            created_by=created_by,
        )
        db.add(task)
        await db.flush()
        return task

    async def update_progress(
        self,
        db: AsyncSession,
        task: QuestionGenerationTask,
        *,
        status: str | None = None,
        stage: str | None = None,
        progress: float | None = None,
        state_snapshot: dict[str, Any] | None = None,
    ) -> None:
        """
        更新任务进度

        :param db: 数据库会话
        :param task: 任务
        :param status: 状态
        :param stage: 阶段
        :param progress: 进度
        :param state_snapshot: 快照
        :return:
        """
        if status is not None:
            task.status = status
        if stage is not None:
            task.stage = stage
        if progress is not None:
            task.progress = progress
        if state_snapshot is not None:
            task.state_snapshot = state_snapshot
        if task.started_time is None and status not in {None, 'pending'}:
            task.started_time = timezone.now()
        await db.flush()

    async def mark_completed(
        self,
        db: AsyncSession,
        task: QuestionGenerationTask,
        *,
        result_summary: dict[str, Any],
    ) -> None:
        """
        标记任务完成

        :param db: 数据库会话
        :param task: 任务
        :param result_summary: 结果摘要
        :return:
        """
        task.status = 'completed'
        task.stage = 'completed'
        task.progress = 1.0
        task.result_summary = result_summary
        task.finished_time = timezone.now()
        await db.flush()

    async def mark_failed(
        self,
        db: AsyncSession,
        task: QuestionGenerationTask,
        *,
        error_code: str,
        error_message: str,
        state_snapshot: dict[str, Any] | None = None,
    ) -> None:
        """
        标记任务失败

        :param db: 数据库会话
        :param task: 任务
        :param error_code: 错误码
        :param error_message: 错误信息
        :param state_snapshot: 中间快照
        :return:
        """
        task.status = 'failed'
        task.stage = 'failed'
        task.progress = 0.0
        task.error_code = error_code
        task.error_message = error_message
        task.finished_time = timezone.now()
        if state_snapshot is not None:
            task.state_snapshot = state_snapshot
        await db.flush()

    async def delete(self, db: AsyncSession, ids: list[int]) -> int:
        """
        删除任务

        :param db: 数据库会话
        :param ids: 任务 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=ids)


class CRUDQuestionGenerationCandidate(CRUDPlus[QuestionGenerationCandidate]):
    """AI 候选题 CRUD"""

    async def get(self, db: AsyncSession, pk: int) -> QuestionGenerationCandidate | None:
        """
        获取候选题

        :param db: 数据库会话
        :param pk: 候选题 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_list(
        self,
        db: AsyncSession,
        *,
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
        stmt = sa.select(self.model)
        if task_id is not None:
            stmt = stmt.where(self.model.task_id == task_id)
        if material_id is not None:
            stmt = stmt.where(self.model.material_id == material_id)
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        stmt = stmt.order_by(self.model.sort_order.asc(), self.model.id.desc())
        result = await db.execute(stmt)
        return result.scalars().all()

    async def update_status(
        self,
        db: AsyncSession,
        candidate: QuestionGenerationCandidate,
        *,
        status: str,
        updated_by: int,
        qc_result: dict[str, Any] | None = None,
    ) -> None:
        """
        更新候选题状态

        :param db: 数据库会话
        :param candidate: 候选题
        :param status: 状态
        :param updated_by: 更新者
        :param qc_result: 质检结果
        :return:
        """
        candidate.status = status
        candidate.updated_by = updated_by
        if qc_result is not None:
            candidate.qc_result = qc_result
        await db.flush()

    async def delete(self, db: AsyncSession, ids: list[int]) -> int:
        """
        删除候选题

        :param db: 数据库会话
        :param ids: 候选题 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=ids)

    async def batch_create_from_agent(
        self,
        db: AsyncSession,
        *,
        task_id: int,
        material_id: int,
        rows: list[dict[str, Any]],
        created_by: int,
        qc_result: dict[str, Any] | None = None,
    ) -> list[QuestionGenerationCandidate]:
        """
        批量创建 agent 候选题

        :param db: 数据库会话
        :param task_id: 任务 ID
        :param material_id: 素材 ID
        :param rows: 候选题数据
        :param created_by: 创建者
        :param qc_result: 质检结果
        :return:
        """
        candidates: list[QuestionGenerationCandidate] = []
        passed = bool(qc_result and qc_result.get('passed'))
        status = 'qc_passed' if passed else 'qc_failed'
        for index, row in enumerate(rows):
            difficulty = row.get('difficulty')
            if difficulty is not None:
                difficulty = Decimal(str(difficulty))
            candidate = self.model(
                task_id=task_id,
                material_id=material_id,
                question_type=str(row.get('question_type') or ''),
                passage_id=row.get('passage_id'),
                selected_passage=str(row.get('selected_passage') or ''),
                question_subtype=row.get('question_subtype'),
                stem=str(row.get('stem') or ''),
                options=list(row.get('options') or []),
                answer_data=dict(row.get('answer_data') or {}),
                analysis=str(row.get('analysis') or ''),
                status=status,
                passage_meta=row.get('passage_meta'),
                blueprint=row.get('blueprint'),
                qc_result=qc_result,
                difficulty=difficulty,
                knowledge_point=row.get('knowledge_point'),
                sort_order=index,
                created_by=created_by,
            )
            db.add(candidate)
            candidates.append(candidate)
        await db.flush()
        return candidates


material_dao: CRUDQuestionGenerationMaterial = CRUDQuestionGenerationMaterial(QuestionGenerationMaterial)
task_dao: CRUDQuestionGenerationTask = CRUDQuestionGenerationTask(QuestionGenerationTask)
candidate_dao: CRUDQuestionGenerationCandidate = CRUDQuestionGenerationCandidate(QuestionGenerationCandidate)
