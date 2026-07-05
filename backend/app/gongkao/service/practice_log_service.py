#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_practice_log import practice_log_dao, practice_module_dao
from backend.app.gongkao.model.practice_log import GongkaoPracticeLog
from backend.app.gongkao.schema.practice_log import (
    CreatePracticeLogParam,
    CreatePracticeModuleParam,
    GetPracticeLogDetail,
    GetPracticeModuleDetail,
    UpdatePracticeLogParam,
    UpdatePracticeModuleParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class PracticeLogService:
    """练习记录服务类"""

    @staticmethod
    def _build_detail(
        log: GongkaoPracticeLog,
        modules: list | None = None,
    ) -> GetPracticeLogDetail:
        detail = GetPracticeLogDetail.model_validate(log)
        if modules is not None:
            detail.modules = [GetPracticeModuleDetail.model_validate(m) for m in modules]
        return detail

    @staticmethod
    def _build_modules_data(
        modules: list[CreatePracticeModuleParam] | list[UpdatePracticeModuleParam],
    ) -> list[dict[str, Any]]:
        """
        构建模块入库数据

        :param modules: 模块参数列表
        :return:
        """
        modules_data = []
        used_seq_no = set()
        for index, module in enumerate(modules):
            data = module.model_dump()
            preferred_seq_no = data.get('seq_no')
            if 'seq_no' not in module.model_fields_set:
                preferred_seq_no = index

            seq_no = PracticeLogService._resolve_seq_no(preferred_seq_no, used_seq_no)
            data['seq_no'] = seq_no
            used_seq_no.add(seq_no)
            modules_data.append(data)

        return modules_data

    @staticmethod
    def _resolve_seq_no(preferred_seq_no: int | None, used_seq_no: set[int]) -> int:
        """
        解析不重复的模块排序号

        :param preferred_seq_no: 首选排序号
        :param used_seq_no: 已使用排序号集合
        :return:
        """
        if preferred_seq_no is not None and preferred_seq_no >= 0 and preferred_seq_no not in used_seq_no:
            return preferred_seq_no

        seq_no = 0
        while seq_no in used_seq_no:
            seq_no += 1

        return seq_no

    @staticmethod
    async def get(*, db: AsyncSession, user_id: int, pk: int) -> GetPracticeLogDetail:
        log = await practice_log_dao.get_by_user(db, pk=pk, user_id=user_id)
        if not log:
            raise errors.NotFoundError(msg='练习记录不存在或无权访问')
        modules = await practice_module_dao.get_by_log_id(db, log_id=log.id)
        return PracticeLogService._build_detail(log, modules)

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        user_id: int,
        material_type: str | None = None,
        material_title: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict:
        stmt = practice_log_dao.get_select(
            user_id=user_id,
            material_type=material_type,
            material_title=material_title,
            start_date=start_date,
            end_date=end_date,
        )
        return await paging_data(db, stmt)

    @staticmethod
    async def create(*, db: AsyncSession, user_id: int, obj: CreatePracticeLogParam, created_by: int) -> GetPracticeLogDetail:
        log = await practice_log_dao.create(db, obj, user_id=user_id, created_by=created_by)
        if obj.modules:
            modules_data = PracticeLogService._build_modules_data(obj.modules)
            modules = await practice_module_dao.batch_create(db, log_id=log.id, modules=modules_data)
        else:
            modules = []
        return PracticeLogService._build_detail(log, modules)

    @staticmethod
    async def update(*, db: AsyncSession, user_id: int, pk: int, obj: UpdatePracticeLogParam) -> GetPracticeLogDetail:
        existing = await practice_log_dao.get_by_user(db, pk=pk, user_id=user_id)
        if not existing:
            raise errors.NotFoundError(msg='练习记录不存在或无权访问')

        await practice_log_dao.update_fields(db, pk=pk, obj=obj)

        if obj.modules is not None:
            await practice_module_dao.delete_by_log_id(db, log_id=pk)
            if obj.modules:
                modules_data = PracticeLogService._build_modules_data(obj.modules)
                await practice_module_dao.batch_create(db, log_id=pk, modules=modules_data)

        await db.flush()
        return await PracticeLogService.get(db=db, user_id=user_id, pk=pk)

    @staticmethod
    async def delete(*, db: AsyncSession, user_id: int, pk: int) -> int:
        existing = await practice_log_dao.get_by_user(db, pk=pk, user_id=user_id)
        if not existing:
            raise errors.NotFoundError(msg='练习记录不存在或无权访问')
        return await practice_log_dao.delete(db, pk)

    @staticmethod
    async def get_trends(*, db: AsyncSession, user_id: int, limit_days: int | None = None) -> dict:
        rows = await practice_module_dao.get_module_trends(db, user_id=user_id, limit_days=limit_days)
        module_map: dict[str, list[dict]] = {}
        for row in rows:
            name = row['module_name']
            if name not in module_map:
                module_map[name] = []
            accuracy = round(row['correct_count'] / row['total_questions'] * 100, 1) if row['total_questions'] > 0 else 0
            avg_seconds = round(row['duration_seconds'] / row['total_questions'], 1) if row['total_questions'] > 0 and row['duration_seconds'] else None
            module_map[name].append({
                'practiced_at': row['practiced_at'],
                'accuracy': accuracy,
                'avg_seconds': avg_seconds,
            })
        return {'module_trends': [{'module_name': k, 'points': v} for k, v in module_map.items()]}


practice_log_service: PracticeLogService = PracticeLogService()
