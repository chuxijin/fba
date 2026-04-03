#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""材料服务类"""
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_material import material_dao
from backend.app.question_bank.model.question import QuestionMaterial
from backend.app.question_bank.schema.material import (
    CreateMaterialParam,
    DeleteMaterialParam,
    LinkQuestionParam,
    MaterialParam,
    UpdateMaterialParam,
)
from backend.common.exception import errors


class MaterialService:
    """材料服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> QuestionMaterial:
        """
        获取材料详情

        :param db: 数据库会话
        :param pk: 材料 ID
        :return:
        """
        material = await material_dao.get(db, pk)
        if not material:
            raise errors.NotFoundError(msg='材料不存在')
        return material

    @staticmethod
    async def get_with_relation(*, db: AsyncSession, pk: int) -> dict:
        """
        获取材料详情（包含关联信息）

        :param db: 数据库会话
        :param pk: 材料 ID
        :return:
        """
        material = await material_dao.get_with_bank(db, pk)
        if not material:
            raise errors.NotFoundError(msg='材料不存在')

        question_count = await material_dao.get_question_count(db, pk)

        return {
            **material.__dict__,
            'bank': {
                'id': material.bank.id,
                'name': material.bank.name,
                'code': material.bank.code or '',
            } if material.bank else None,
            'question_count': question_count,
        }

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        params: MaterialParam,
    ) -> Sequence[QuestionMaterial]:
        """
        获取材料列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        return await material_dao.get_list(db, params)

    @staticmethod
    async def get_by_bank(
        *,
        db: AsyncSession,
        bank_id: int,
        is_active: bool | None = None,
    ) -> Sequence[QuestionMaterial]:
        """
        获取题库材料列表

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param is_active: 是否启用
        :return:
        """
        return await material_dao.get_by_bank(db, bank_id, is_active)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateMaterialParam, created_by: int) -> QuestionMaterial:
        """
        创建材料

        :param db: 数据库会话
        :param obj: 创建材料参数
        :param created_by: 创建者用户 ID
        :return:
        """
        # 验证题库存在
        bank = await bank_dao.get(db, obj.bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')

        # 检查标题是否重复
        existing = await material_dao.get_by_title(db, obj.bank_id, obj.title)
        if existing:
            raise errors.ConflictError(msg='该题库中已存在同名材料')

        material = await material_dao.create(db, obj, created_by=created_by)
        await db.flush()
        return material

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateMaterialParam, updated_by: int) -> int:
        """
        更新材料

        :param db: 数据库会话
        :param pk: 材料 ID
        :param obj: 更新材料参数
        :param updated_by: 更新者用户 ID
        :return:
        """
        material = await material_dao.get(db, pk)
        if not material:
            raise errors.NotFoundError(msg='材料不存在')

        # 验证题库存在
        bank = await bank_dao.get(db, obj.bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')

        # 检查标题是否重复（排除自身）
        existing = await material_dao.get_by_title(db, obj.bank_id, obj.title)
        if existing and existing.id != pk:
            raise errors.ConflictError(msg='该题库中已存在同名材料')

        return await material_dao.update(db, pk, obj, updated_by=updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteMaterialParam) -> int:
        """
        删除材料

        :param db: 数据库会话
        :param obj: 删除材料参数
        :return:
        """
        # 检查是否有关联的题目
        for material_id in obj.ids:
            count = await material_dao.get_question_count(db, material_id)
            if count > 0:
                raise errors.ConflictError(msg=f'材料 ID {material_id} 仍有 {count} 道题目关联，请先解除关联')

        return await material_dao.delete(db, obj.ids)

    @staticmethod
    async def link_questions(
        *,
        db: AsyncSession,
        pk: int,
        obj: LinkQuestionParam,
    ) -> None:
        """
        关联题目到材料

        :param db: 数据库会话
        :param pk: 材料 ID
        :param obj: 关联题目参数
        :return:
        """
        material = await material_dao.get(db, pk)
        if not material:
            raise errors.NotFoundError(msg='材料不存在')

        await material_dao.link_questions(db, pk, obj.question_ids)

    @staticmethod
    async def unlink_questions(
        *,
        db: AsyncSession,
        pk: int,
        obj: LinkQuestionParam,
    ) -> int:
        """
        解除题目与材料的关联

        :param db: 数据库会话
        :param pk: 材料 ID
        :param obj: 解除关联参数
        :return:
        """
        material = await material_dao.get(db, pk)
        if not material:
            raise errors.NotFoundError(msg='材料不存在')

        return await material_dao.unlink_questions(db, pk, obj.question_ids)


material_service: MaterialService = MaterialService()

