#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from datetime import date
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_practice_log import practice_log_dao, practice_module_dao
from backend.app.gongkao.model.practice_log import GongkaoPracticeLog
from backend.app.gongkao.schema.practice_log import (
    CreatePracticeLogParam,
    CreatePracticeModuleParam,
    GetPracticeLogDetail,
    GetPracticeModuleDetail,
    GetPracticeSubModuleDetail,
    ImportPracticeReportParam,
    ImportPracticeReportResult,
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
            parents = {
                m.id: GetPracticeModuleDetail.model_validate(m)
                for m in modules
                if getattr(m, 'parent_id', None) is None
            }
            for module in modules:
                if getattr(module, 'parent_id', None) in parents:
                    parents[module.parent_id].children.append(GetPracticeSubModuleDetail.model_validate(module))
            detail.modules = list(parents.values())
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
        page = await paging_data(db, stmt, schema_cls=GetPracticeLogDetail)
        items = page['items']
        modules = await practice_module_dao.get_by_log_ids(db, [item['id'] for item in items])
        grouped: dict[int, list] = {}
        for module in modules:
            grouped.setdefault(module.log_id, []).append(module)
        page['items'] = [
            PracticeLogService._build_detail(item, grouped.get(item['id'], [])).model_dump() for item in items
        ]
        return page

    @staticmethod
    async def create(
        *, db: AsyncSession, user_id: int, obj: CreatePracticeLogParam, created_by: int
    ) -> GetPracticeLogDetail:
        log = await practice_log_dao.create(db, obj, user_id=user_id, created_by=created_by)
        if obj.modules:
            modules_data = PracticeLogService._build_modules_data(obj.modules)
            modules = await practice_module_dao.batch_create(db, log_id=log.id, modules=modules_data)
        else:
            modules = []
        return PracticeLogService._build_detail(log, modules)

    @staticmethod
    async def import_report(
        *, db: AsyncSession, user_id: int, obj: ImportPracticeReportParam
    ) -> ImportPracticeReportResult:
        existing = await practice_log_dao.get_by_source(
            db, user_id=user_id, source_platform=obj.source_platform, source_key=obj.source_key
        )
        if existing:
            return ImportPracticeReportResult(
                created=False, record=await PracticeLogService.get(db=db, user_id=user_id, pk=existing.id)
            )
        try:
            # 唯一约束处理并发重复点击；子事务失败不会回滚整个请求会话。
            async with db.begin_nested():
                detail = await PracticeLogService.create(db=db, user_id=user_id, obj=obj, created_by=user_id)
            return ImportPracticeReportResult(created=True, record=detail)
        except IntegrityError:
            existing = await practice_log_dao.get_by_source(
                db, user_id=user_id, source_platform=obj.source_platform, source_key=obj.source_key
            )
            if existing is None:
                raise
            return ImportPracticeReportResult(
                created=False, record=await PracticeLogService.get(db=db, user_id=user_id, pk=existing.id)
            )

    @staticmethod
    async def update(*, db: AsyncSession, user_id: int, pk: int, obj: UpdatePracticeLogParam) -> GetPracticeLogDetail:
        existing = await practice_log_dao.get_by_user(db, pk=pk, user_id=user_id)
        if not existing:
            raise errors.NotFoundError(msg='练习记录不存在或无权访问')

        merged = GetPracticeLogDetail.model_validate(existing).model_dump()
        merged.update(obj.model_dump(exclude_unset=True))
        try:
            CreatePracticeLogParam.model_validate(merged)
        except ValidationError as exc:
            raise errors.RequestError(msg='题数、正确数、未答数或模块统计不合法') from exc
        changed_date = obj.practiced_at is not None and obj.practiced_at != existing.practiced_at
        await practice_log_dao.update_fields(db, pk=pk, obj=obj)
        if changed_date:
            existing.time_source = 'manual'

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
            accuracy = (
                round(row['correct_count'] / row['total_questions'] * 100, 1) if row['total_questions'] > 0 else 0
            )
            avg_seconds = (
                round(row['duration_seconds'] / row['total_questions'], 1)
                if row['total_questions'] > 0 and row['duration_seconds']
                else None
            )
            module_map[name].append({
                'practiced_at': row['practiced_at'],
                'accuracy': accuracy,
                'avg_seconds': avg_seconds,
            })
        return {'module_trends': [{'module_name': k, 'points': v} for k, v in module_map.items()]}

    @staticmethod
    def _comparison_series(records: list[GetPracticeLogDetail]) -> list[dict[str, Any]]:
        """按完整模块路径比较每次练习，不跨层合计、不按日期覆盖数据"""
        series: dict[str, dict[str, Any]] = {}

        def append(log: GetPracticeLogDetail, node: Any, path: list[str], level: str) -> None:
            key = json.dumps(path, ensure_ascii=False, separators=(',', ':'))
            entry = series.setdefault(key, {'key': key, 'path': path, 'level': level, 'points': []})
            total, correct, duration = node.total_questions, node.correct_count, node.duration_seconds
            unanswered = node.unanswered_count
            entry['points'].append({
                'point_id': f'{log.id}:{level}:{node.id}',
                'record_id': log.id,
                'record_title': log.material_title,
                'source_platform': log.source_platform,
                'practiced_at': log.practiced_at.isoformat(),
                'source_updated_at': log.source_updated_at.isoformat() if log.source_updated_at else None,
                'total_questions': total,
                'correct_count': correct,
                'unanswered_count': unanswered,
                'wrong_count': total - correct - unanswered if unanswered is not None else None,
                'accuracy': round(correct / total * 100, 2) if total else None,
                'duration_seconds': duration,
                'avg_seconds': round(duration / total, 2) if duration is not None and total else None,
            })

        for log in records:
            subject = log.subject_name.strip() or '行测'
            append(log, log, [subject], 'subject')
            for module in log.modules:
                path = [subject, module.module_name.strip()]
                append(log, module, path, 'module')
                for child in module.children:
                    append(log, child, [*path, child.module_name.strip()], 'submodule')
        return list(series.values())

    @staticmethod
    async def get_comparisons(
        *,
        db: AsyncSession,
        user_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
        source_platform: str | None = None,
    ) -> dict[str, Any]:
        if start_date and end_date and start_date > end_date:
            raise errors.RequestError(msg='开始日期不能晚于结束日期')
        records = list(
            await practice_log_dao.get_comparison_records(
                db, user_id=user_id, start_date=start_date, end_date=end_date, source_platform=source_platform
            )
        )
        limited = len(records) > 500
        records = records[:500]
        modules = await practice_module_dao.get_by_log_ids(db, [log.id for log in records])
        grouped: dict[int, list] = {}
        for module in modules:
            grouped.setdefault(module.log_id, []).append(module)
        details = [PracticeLogService._build_detail(log, grouped.get(log.id, [])) for log in reversed(records)]
        return {
            'series': PracticeLogService._comparison_series(details),
            'limited': limited,
            'record_count': len(details),
        }


practice_log_service: PracticeLogService = PracticeLogService()
