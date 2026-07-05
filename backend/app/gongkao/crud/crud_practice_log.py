#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import date

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model.practice_log import GongkaoPracticeLog, GongkaoPracticeModule
from backend.app.gongkao.schema.practice_log import CreatePracticeLogParam, UpdatePracticeLogParam


class CRUDPracticeLog(CRUDPlus[GongkaoPracticeLog]):
    """练习记录数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GongkaoPracticeLog | None:
        return await self.select_model(db, pk)

    async def get_by_user(self, db: AsyncSession, pk: int, user_id: int) -> GongkaoPracticeLog | None:
        return await self.select_model_by_column(db, id=pk, user_id=user_id)

    def get_select(
        self,
        user_id: int,
        material_type: str | None = None,
        material_title: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Select:
        stmt = select(GongkaoPracticeLog).where(GongkaoPracticeLog.user_id == user_id)
        if material_type is not None:
            stmt = stmt.where(GongkaoPracticeLog.material_type == material_type)
        if material_title is not None:
            stmt = stmt.where(GongkaoPracticeLog.material_title.like(f'%{material_title}%'))
        if start_date is not None:
            stmt = stmt.where(GongkaoPracticeLog.practiced_at >= start_date)
        if end_date is not None:
            stmt = stmt.where(GongkaoPracticeLog.practiced_at <= end_date)
        return stmt.order_by(GongkaoPracticeLog.practiced_at.desc(), GongkaoPracticeLog.created_time.desc())

    async def create(self, db: AsyncSession, obj: CreatePracticeLogParam, user_id: int, created_by: int) -> GongkaoPracticeLog:
        data = obj.model_dump(exclude={'modules'})
        data['user_id'] = user_id
        data['created_by'] = created_by
        if data.get('total_questions', 0) > 0:
            data['accuracy_rate'] = round(data['correct_count'] / data['total_questions'] * 100, 2)
        log = self.model(**data)
        db.add(log)
        await db.flush()
        return log

    async def update_fields(self, db: AsyncSession, pk: int, obj: UpdatePracticeLogParam) -> int:
        update_data = obj.model_dump(exclude={'modules'}, exclude_unset=True)
        if 'total_questions' in update_data and 'correct_count' in update_data:
            total = update_data['total_questions']
            correct = update_data['correct_count']
            if total > 0:
                update_data['accuracy_rate'] = round(correct / total * 100, 2)
        elif 'total_questions' in update_data or 'correct_count' in update_data:
            existing = await self.get(db, pk)
            if existing:
                total = update_data.get('total_questions', existing.total_questions)
                correct = update_data.get('correct_count', existing.correct_count)
                if total > 0:
                    update_data['accuracy_rate'] = round(correct / total * 100, 2)
        return await self.update_model_by_column(db, update_data, id=pk)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model(db, pk)

    async def get_calendar_stats(
        self, db: AsyncSession, user_id: int, year: int, month: int | None = None
    ) -> Sequence[GongkaoPracticeLog]:
        filters = {'user_id': user_id}
        if month is not None:
            stmt = select(GongkaoPracticeLog).where(
                GongkaoPracticeLog.user_id == user_id,
                func.date_trunc('month', GongkaoPracticeLog.practiced_at) == func.date(f'{year}-{month:02d}-01'),
            )
        else:
            stmt = select(GongkaoPracticeLog).where(
                GongkaoPracticeLog.user_id == user_id,
                func.date_trunc('year', GongkaoPracticeLog.practiced_at) == func.date(f'{year}-01-01'),
            )
        stmt = stmt.order_by(GongkaoPracticeLog.practiced_at.desc())
        result = await db.execute(stmt)
        return result.scalars().all()


class CRUDPracticeModule(CRUDPlus[GongkaoPracticeModule]):
    """练习模块数据库操作类"""

    async def get_by_log_id(self, db: AsyncSession, log_id: int) -> Sequence[GongkaoPracticeModule]:
        return await self.select_models_order(db, 'seq_no', 'asc', log_id=log_id)

    async def batch_create(self, db: AsyncSession, log_id: int, modules: list[dict]) -> list[GongkaoPracticeModule]:
        created = []
        for data in modules:
            if data.get('total_questions', 0) > 0:
                data['accuracy_rate'] = round(data['correct_count'] / data['total_questions'] * 100, 2)
            module = self.model(log_id=log_id, **data)
            db.add(module)
            created.append(module)
        await db.flush()
        return created

    async def delete_by_log_id(self, db: AsyncSession, log_id: int) -> int:
        stmt = delete(GongkaoPracticeModule).where(GongkaoPracticeModule.log_id == log_id)
        result = await db.execute(stmt)
        return result.rowcount

    async def get_module_trends(
        self, db: AsyncSession, user_id: int, limit_days: int | None = None
    ) -> list[dict]:
        """获取模块趋势数据"""
        stmt = (
            select(
                GongkaoPracticeModule.module_name,
                GongkaoPracticeLog.practiced_at,
                GongkaoPracticeModule.total_questions,
                GongkaoPracticeModule.correct_count,
                GongkaoPracticeModule.duration_seconds,
            )
            .join(GongkaoPracticeLog, GongkaoPracticeLog.id == GongkaoPracticeModule.log_id)
            .where(GongkaoPracticeLog.user_id == user_id)
            .order_by(GongkaoPracticeLog.practiced_at.asc(), GongkaoPracticeModule.seq_no.asc())
        )
        if limit_days:
            stmt = stmt.where(
                GongkaoPracticeLog.practiced_at >= func.current_date() - limit_days
            )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            {
                'module_name': row[0],
                'practiced_at': str(row[1]),
                'total_questions': row[2],
                'correct_count': row[3],
                'duration_seconds': row[4],
            }
            for row in rows
        ]


practice_log_dao: CRUDPracticeLog = CRUDPracticeLog(GongkaoPracticeLog)
practice_module_dao: CRUDPracticeModule = CRUDPracticeModule(GongkaoPracticeModule)
