#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.crud.crud_exercise import exercise_dao
from backend.app.jia.model.exercise import Exercise
from backend.app.jia.schema.exercise import CreateExerciseParam, GetExerciseListResponse, UpdateExerciseParam
from backend.common.log import log
from backend.common.pagination import paging_data
from backend.utils.embedding import embed


class ExerciseService:

    @staticmethod
    async def get(db: AsyncSession, pk: int) -> Exercise | None:
        """获取动作详情"""
        return await exercise_dao.get(db, pk)

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        name: str | None = None,
        semantic: bool = False,
        limit: int = 20,
    ) -> dict[str, Any] | list[Exercise]:
        """
        获取动作列表（支持普通搜索和语义搜索）

        :param db: 数据库会话
        :param name: 动作名称
        :param semantic: 是否启用语义搜索
        :param limit: 语义搜索时的返回数量
        :return:
        """
        if semantic and name:
            # 语义搜索模式
            try:
                vector = await embed(name)
                return await exercise_dao.search_by_vector(db, vector, limit=limit)
            except Exception as e:
                log.error(f'语义搜索向量化失败: {e}')
                # 降级为普通搜索
                select_stmt = await exercise_dao.get_list(name=name)
                return await paging_data(db, select_stmt, schema_cls=GetExerciseListResponse)

        # 普通分页搜索
        select_stmt = await exercise_dao.get_list(name=name)
        return await paging_data(db, select_stmt, schema_cls=GetExerciseListResponse)

    @staticmethod
    async def get_all(db: AsyncSession) -> Sequence[Exercise]:
        """获取所有动作"""
        return await exercise_dao.get_all(db)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateExerciseParam, created_by: int) -> Exercise:
        """
        创建动作（自动向量化）

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        vector = await ExerciseService._generate_vector(db, obj)
        return await exercise_dao.create(db, obj, created_by, vector=vector)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateExerciseParam, updated_by: int) -> int:
        """
        更新动作（自动更新向量）

        :param db: 数据库会话
        :param pk: 动作 ID
        :param obj: 更新参数
        :param updated_by: 更新者 ID
        :return:
        """
        # 检查是否需要更新向量
        update_data = obj.model_dump(exclude_unset=True)
        vector = None
        if any(k in update_data for k in ['name_zh', 'name_en', 'category', 'instructions', 'primary_muscles']):
            # 获取当前数据合并后重新生成向量
            current = await exercise_dao.get(db, pk)
            if current:
                merged_obj = ExerciseService._merge_for_vector(current, obj)
                vector = await ExerciseService._generate_vector(db, merged_obj)

        return await exercise_dao.update(db, pk, obj, updated_by, vector=vector)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """删除动作"""
        return await exercise_dao.delete(db, pk)

    @staticmethod
    async def _generate_vector(db: AsyncSession, obj: CreateExerciseParam | Exercise) -> list[float] | None:
        """
        生成动作向量

        :param db: 数据库会话
        :param obj: 动作数据
        :return:
        """
        # 组合文本用于向量化
        text_parts = []

        name_zh = getattr(obj, 'name_zh', None)
        name_en = getattr(obj, 'name_en', None)
        category = getattr(obj, 'category', None)
        primary_muscles = getattr(obj, 'primary_muscles', None)
        instructions = getattr(obj, 'instructions', None)

        if name_zh:
            text_parts.append(f'名称: {name_zh}')
        if name_en:
            text_parts.append(f'英文名: {name_en}')
        if category:
            text_parts.append(f'分类: {category}')
        if primary_muscles:
            muscles_str = ', '.join(primary_muscles) if isinstance(primary_muscles, list) else primary_muscles
            text_parts.append(f'肌肉群: {muscles_str}')
        if instructions:
            instr_str = ' '.join(instructions[:3]) if isinstance(instructions, list) else instructions
            text_parts.append(f'动作说明: {instr_str}')

        text_to_embed = ', '.join(text_parts).strip()
        if not text_to_embed:
            return None

        try:
            return await embed(text_to_embed)
        except Exception as e:
            log.error(f'动作向量化失败: {e}')
            return None

    @staticmethod
    def _merge_for_vector(current: Exercise, obj: UpdateExerciseParam) -> Exercise:
        """合并当前数据和更新数据用于向量生成"""
        # 创建一个临时对象用于生成向量
        class MergedData:
            pass

        merged = MergedData()
        update_data = obj.model_dump(exclude_unset=True)

        merged.name_zh = update_data.get('name_zh', current.name_zh)
        merged.name_en = update_data.get('name_en', current.name_en)
        merged.category = update_data.get('category', current.category)
        merged.primary_muscles = update_data.get('primary_muscles', current.primary_muscles)
        merged.instructions = update_data.get('instructions', current.instructions)

        return merged


exercise_service = ExerciseService()
