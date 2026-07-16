#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model.question import MaterialAnchor, QuestionInteractionAnnotation
from backend.app.question_bank.schema.interaction import (
    CreateMaterialAnchorParam,
    CreateQuestionInteractionAnnotationParam,
    MaterialAnchorQueryParam,
    QuestionInteractionAnnotationQueryParam,
    UpdateMaterialAnchorParam,
    UpdateQuestionInteractionAnnotationParam,
)
from backend.utils.timezone import timezone


class CRUDMaterialAnchor(CRUDPlus[MaterialAnchor]):
    """材料锚点数据库操作类"""

    async def get(self, db: AsyncSession, anchor_id: int) -> MaterialAnchor | None:
        """
        获取材料锚点

        :param db: 数据库会话
        :param anchor_id: 锚点 ID
        :return:
        """
        return await self.select_model_by_column(db, id=anchor_id)

    async def get_by_ids(self, db: AsyncSession, anchor_ids: list[int]) -> Sequence[MaterialAnchor]:
        """
        批量获取材料锚点

        :param db: 数据库会话
        :param anchor_ids: 锚点 ID 列表
        :return:
        """
        if not anchor_ids:
            return []
        stmt = select(self.model).where(self.model.id.in_(anchor_ids), self.model.deleted == 0)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_list(self, db: AsyncSession, params: MaterialAnchorQueryParam) -> Sequence[MaterialAnchor]:
        """
        获取材料锚点列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        stmt = select(self.model).where(self.model.deleted == 0)
        if params.material_id is not None:
            stmt = stmt.where(self.model.material_id == params.material_id)
        if params.anchor_type is not None:
            stmt = stmt.where(self.model.anchor_type == params.anchor_type)
        if params.role is not None:
            stmt = stmt.where(self.model.role == params.role)
        if params.status is not None:
            stmt = stmt.where(self.model.status == params.status)
        stmt = stmt.order_by(self.model.start_offset.asc().nulls_last(), self.model.id.asc())
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(self, db: AsyncSession, obj: CreateMaterialAnchorParam, *, created_by: int) -> MaterialAnchor:
        """
        创建材料锚点

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者用户 ID
        :return:
        """
        data = obj.model_dump()
        data['created_by'] = created_by
        anchor = self.model(**data)
        db.add(anchor)
        return anchor

    async def update(self, db: AsyncSession, anchor_id: int, obj: UpdateMaterialAnchorParam, *, updated_by: int) -> int:
        """
        更新材料锚点

        :param db: 数据库会话
        :param anchor_id: 锚点 ID
        :param obj: 更新参数
        :param updated_by: 更新者用户 ID
        :return:
        """
        data = obj.model_dump(exclude_unset=True)
        if not data:
            return 0
        data['updated_by'] = updated_by
        stmt = update(self.model).where(self.model.id == anchor_id, self.model.deleted == 0).values(**data)
        result = await db.execute(stmt)
        return result.rowcount or 0

    async def delete(self, db: AsyncSession, anchor_ids: list[int]) -> int:
        """
        删除材料锚点

        :param db: 数据库会话
        :param anchor_ids: 锚点 ID 列表
        :return:
        """
        if not anchor_ids:
            return 0
        return await self.delete_model_by_column(
            db,
            allow_multiple=True,
            logical_deletion=True,
            deleted_flag_column='deleted',
            deleted_flag_value=self.model.id,
            deleted_at_column='deleted_time',
            deleted_at_factory=timezone.now(),
            id__in=anchor_ids,
            deleted=0,
        )


class CRUDQuestionInteractionAnnotation(CRUDPlus[QuestionInteractionAnnotation]):
    """题目交互标注数据库操作类"""

    async def get(self, db: AsyncSession, annotation_id: int) -> QuestionInteractionAnnotation | None:
        """
        获取题目交互标注

        :param db: 数据库会话
        :param annotation_id: 标注 ID
        :return:
        """
        return await self.select_model_by_column(db, id=annotation_id)

    async def get_list(
        self, db: AsyncSession, params: QuestionInteractionAnnotationQueryParam
    ) -> Sequence[QuestionInteractionAnnotation]:
        """
        获取题目交互标注列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        stmt = select(self.model).where(self.model.deleted == 0)
        if params.question_id is not None:
            stmt = stmt.where(self.model.question_id == params.question_id)
        if params.material_id is not None:
            stmt = stmt.where(self.model.material_id == params.material_id)
        if params.interaction_type is not None:
            stmt = stmt.where(self.model.interaction_type == params.interaction_type)
        if params.is_default is not None:
            stmt = stmt.where(self.model.is_default.is_(params.is_default))
        if params.status is not None:
            stmt = stmt.where(self.model.status == params.status)
        stmt = stmt.order_by(self.model.question_id.asc(), self.model.version_no.desc(), self.model.id.desc())
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_default_by_question_ids(
        self,
        db: AsyncSession,
        question_ids: list[int],
        interaction_type: str | None = None,
    ) -> Sequence[QuestionInteractionAnnotation]:
        """
        批量获取默认可用交互标注

        :param db: 数据库会话
        :param question_ids: 题目 ID 列表
        :param interaction_type: 交互类型
        :return:
        """
        if not question_ids:
            return []
        stmt = select(self.model).where(
            self.model.question_id.in_(question_ids),
            self.model.is_default.is_(True),
            self.model.status == 10,
            self.model.deleted == 0,
        )
        if interaction_type:
            stmt = stmt.where(self.model.interaction_type == interaction_type)
        stmt = stmt.order_by(self.model.version_no.desc(), self.model.id.desc())
        result = await db.execute(stmt)
        return result.scalars().all()

    async def unset_default(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        interaction_type: str,
        exclude_id: int | None = None,
    ) -> int:
        """
        取消同题同类型默认标注

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param interaction_type: 交互类型
        :param exclude_id: 排除标注 ID
        :return:
        """
        stmt = (
            update(self.model)
            .where(
                self.model.question_id == question_id,
                self.model.interaction_type == interaction_type,
                self.model.is_default.is_(True),
                self.model.deleted == 0,
            )
            .values(is_default=False)
        )
        if exclude_id is not None:
            stmt = stmt.where(self.model.id != exclude_id)
        result = await db.execute(stmt)
        return result.rowcount or 0

    async def create(
        self,
        db: AsyncSession,
        obj: CreateQuestionInteractionAnnotationParam,
        *,
        created_by: int,
    ) -> QuestionInteractionAnnotation:
        """
        创建题目交互标注

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者用户 ID
        :return:
        """
        data = obj.model_dump()
        data['created_by'] = created_by
        annotation = self.model(**data)
        db.add(annotation)
        return annotation

    async def update(
        self,
        db: AsyncSession,
        annotation_id: int,
        obj: UpdateQuestionInteractionAnnotationParam,
        *,
        updated_by: int,
    ) -> int:
        """
        更新题目交互标注

        :param db: 数据库会话
        :param annotation_id: 标注 ID
        :param obj: 更新参数
        :param updated_by: 更新者用户 ID
        :return:
        """
        data = obj.model_dump(exclude_unset=True)
        if not data:
            return 0
        data['updated_by'] = updated_by
        stmt = update(self.model).where(self.model.id == annotation_id, self.model.deleted == 0).values(**data)
        result = await db.execute(stmt)
        return result.rowcount or 0

    async def delete(self, db: AsyncSession, annotation_ids: list[int]) -> int:
        """
        删除题目交互标注

        :param db: 数据库会话
        :param annotation_ids: 标注 ID 列表
        :return:
        """
        if not annotation_ids:
            return 0
        return await self.delete_model_by_column(
            db,
            allow_multiple=True,
            logical_deletion=True,
            deleted_flag_column='deleted',
            deleted_flag_value=self.model.id,
            deleted_at_column='deleted_time',
            deleted_at_factory=timezone.now(),
            id__in=annotation_ids,
            deleted=0,
        )


material_anchor_dao: CRUDMaterialAnchor = CRUDMaterialAnchor(MaterialAnchor)
question_interaction_annotation_dao: CRUDQuestionInteractionAnnotation = CRUDQuestionInteractionAnnotation(
    QuestionInteractionAnnotation
)
